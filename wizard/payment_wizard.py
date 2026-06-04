from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class BmPaymentWizard(models.TransientModel):
    """
    Interactive checkout cash desk pop-up overlay window to process payments.
    """

    _name = "bm.payment.wizard"
    _description = "Checkout Payment Processing Wizard"

    order_id = fields.Many2one(
        "bm.order", string="Order Number", required=True, readonly=True
    )

    card_id = fields.Many2one(
        "bm.loyalty.card",
        string="Loyalty Card",
        readonly=False,
        help="The customer loyalty card used for this payment. Can be changed by the cashier.",
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Customer Name",
        related="order_id.partner_id",
        readonly=True,
    )

    amount_to_pay = fields.Float(
        string="Total Order Amount",
        compute="_compute_wizard_financial_totals",
        readonly=True,
        digits=(16, 2),
        help="The total money amount from the sales order that needs to be paid.",
    )

    available_cashback = fields.Float(
        string="Available Cashback Points",
        compute="_compute_cashback_data",
        readonly=True,
        digits=(16, 2),
        help="The current cashback points balance that this customer.",
    )

    cash_paid = fields.Float(
        string="Cash Money Received",
        required=True,
        digits=(16, 2),
        help="The cash money received from the customer.",
    )

    cashback_paid = fields.Float(
        string="Cashback Points to Use",
        required=True,
        default=0.0,
        digits=(16, 2),
        help="How many cashback points the customer wants to use to pay for this check.",
    )

    total_received = fields.Float(
        string="Total Money Received",
        compute="_compute_cash_desk_calculations",
        digits=(16, 2),
        help="The sum of cash money received plus the cashback points used.",
    )

    change_amount = fields.Float(
        string="Change to Return",
        compute="_compute_cash_desk_calculations",
        digits=(16, 2),
        help="The change money to return to the customer if they paid more than the order cost.",
    )

    remaining_debt = fields.Float(
        string="New Debt Amount",
        compute="_compute_cash_desk_calculations",
        digits=(16, 2),
        help="The missing money amount that will be sent to the customer debt.",
    )

    allow_debt = fields.Boolean(
        string="Send Balance to Debt",
        default=False,
        help="Check this box if you want to put the missing money amount into the customer debt.",
    )

    discount_amount_wizard = fields.Float(
        string="Discount Amount",
        compute="_compute_wizard_financial_totals",
        readonly=True,
        store=False,
    )

    @api.model
    def default_get(self, fields_list):
        """
        Pre-populates order and card contexts directly from active execution stream.
        """
        res = super().default_get(fields_list)
        active_id = self.env.context.get("active_id")
        if self.env.context.get("active_model") == "bm.order" and active_id:
            order = self.env["bm.order"].browse(active_id)
            res["order_id"] = order.id
            res["card_id"] = order.card_id.id if order.card_id else False
            res["cash_paid"] = order.amount_total
        return res

    @api.depends("card_id", "order_id")
    def _compute_wizard_financial_totals(self):
        """
        Single unified recalculation core computing net payments and monetary discount
        values synchronously inside a single memory loop to prevent ORM cache racing.
        """
        for wizard in self:
            if wizard.order_id:
                # 1. Fetch the raw untaxed base sum from the linked Sales Order document
                base_untaxed = wizard.order_id.amount_untaxed

                # 2. Extract discount percentage rate from the currently selected wizard card
                discount_rate = (
                    wizard.card_id.discount_percent if wizard.card_id else 0.0
                )

                # 3. Synchronously recalculate net price on the fly (Net Amount)
                wizard.amount_to_pay = base_untaxed * (1.0 - (discount_rate / 100.0))

                # 4. Synchronously compute explicit monetary value representation of the discount
                wizard.discount_amount_wizard = base_untaxed - wizard.amount_to_pay
            else:
                wizard.amount_to_pay = 0.0
                wizard.discount_amount_wizard = 0.0

    @api.depends("partner_id", "partner_id.total_cashback_balance")
    def _compute_cashback_data(self):
        """
        Extracts single joint cashback wallet balance directly from customer persistence layer.
        """
        for wizard in self:
            wizard.available_cashback = (
                wizard.partner_id.total_cashback_balance if wizard.partner_id else 0.0
            )

    @api.depends("cash_paid", "cashback_paid", "amount_to_pay")
    def _compute_cash_desk_calculations(self):
        """
        Performs interactive, real-time checkout math calculations inside user viewport memory.
        Evaluates payments, computes change due, or calculates remaining debt gaps.
        """
        for wizard in self:
            received = wizard.cash_paid + wizard.cashback_paid
            wizard.total_received = received

            if received >= wizard.amount_to_pay:
                wizard.change_amount = received - wizard.amount_to_pay
                wizard.remaining_debt = 0.0
            else:
                wizard.change_amount = 0.0
                wizard.remaining_debt = wizard.amount_to_pay - received

    def action_process_sale(self):
        """
        Processes payment logic, alters single customer cashback balances,
        validates credit limitations, posts sub-ledger entries and closes workflow.
        """
        self.ensure_one()

        if self.cashback_paid > self.available_cashback:
            raise ValidationError(
                _(
                    "Cashier Fraud Blocked! Cannot redeem more cashback (%s) than available "
                    "on the customer joint single wallet balance (%s)."
                )
                % (self.cashback_paid, self.available_cashback)
            )

        if self.remaining_debt > 0.0:
            if not self.allow_debt:
                raise ValidationError(
                    _(
                        "Insufficient Funds! Received payment totals do not match the required net amount. "
                        "Please fill full amount or check 'Post Balance to Debt' checkbox to proceed credit."
                    )
                )

            if not self.card_id:
                raise ValidationError(
                    _(
                        "Credit Failure! Anonymous debt accumulation is restricted. "
                        "A valid non-blocked customer loyalty card must be linked to process credit sales."
                    )
                )

            future_debt_total = self.card_id.current_debt + self.remaining_debt
            if future_debt_total > self.card_id.credit_limit:
                raise ValidationError(
                    _(
                        "Credit Cap Breach! The requested credit amount will push total card debt to %s, "
                        "which severely violates the assigned card credit threshold (%s)."
                    )
                    % (future_debt_total, self.card_id.credit_limit)
                )

        if self.cashback_paid > 0.0:
            self.partner_id.total_cashback_balance -= self.cashback_paid

        if self.card_id and self.card_id.cashback_percent > 0.0:
            earned_cashback = self.order_id.amount_untaxed * (
                self.card_id.cashback_percent / 100.0
            )
            self.partner_id.total_cashback_balance += earned_cashback

        if self.remaining_debt > 0.0:
            self.env["bm.debt.ledger"].create(
                {
                    "partner_id": self.partner_id.id,
                    "card_id": self.card_id.id,
                    "amount": self.remaining_debt,
                    "direction": "increase",
                    "res_model": self.order_id._name,
                    "res_id": self.order_id.id,
                }
            )

        self.order_id.write(
            {"card_id": self.card_id.id if self.card_id else False, "state": "done"}
        )
        self.order_id._compute_order_totals()

        return {
            "name": "Sales Orders Journal",
            "type": "ir.actions.act_window",
            "res_model": "bm.order",
            "view_mode": "list,calendar,form",
            "target": "current",
        }
