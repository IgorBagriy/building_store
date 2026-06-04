from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class BmLoyaltyCard(models.Model):
    """
    Manages professional contractors loyalty cards, stage lifecycle, and thresholds.
    """

    _name = "bm.loyalty.card"
    _description = "Master Loyalty Card"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "issue_date desc, id desc"

    name = fields.Char(
        string="Card Number",
        required=True,
        copy=False,
        index=True,
        tracking=True,
        help="Unique alpha-numeric identifier or physical code of the loyalty card.",
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )

    issue_date = fields.Date(
        string="Issue Date",
        required=True,
        copy=False,
        default=fields.Date.context_today,
    )

    discount_percent = fields.Float(
        string="Discount (%)",
        default=0.0,
        digits=(16, 2),
        tracking=True,
        help="Direct discount percentage applied to order lines.",
    )

    cashback_percent = fields.Float(
        string="Cashback Earn (%)",
        default=0.0,
        digits=(16, 2),
        tracking=True,
        help="The additional percentage credited to the customer as cashback.",
    )

    credit_limit = fields.Float(
        string="Assigned Credit Limit",
        default=0.0,
        digits=(16, 2),
        tracking=True,
        help="The maximum allowable debt threshold permitted for this specific card.",
    )

    debt_ledger_ids = fields.One2many(
        "bm.debt.ledger", "card_id", string="Debt Movements"
    )

    order_ids = fields.One2many("bm.order", "card_id", string="Linked Sales Orders")

    current_debt = fields.Float(
        string="Current Debt Balance",
        compute="_compute_current_debt",
        store=True,
        digits=(16, 2),
        tracking=True,
    )

    total_sales_volume = fields.Float(
        string="Total Sales Volume",
        compute="_compute_sales_volume",
        store=True,
        digits=(16, 2),
        tracking=True,
    )

    state = fields.Selection(
        [("new", "New Card"), ("active", "Active"), ("blocked", "Blocked")],
        string="Status",
        default="new",
        compute="_compute_card_state",
        store=True,
        required=True,
        copy=False,
        index=True,
        tracking=True,
        inverse="_inverse_card_state",
        group_expand="_read_group_states",
    )

    _unique_name = models.Constraint(
        "unique(name)", "The loyalty card number must be unique!"
    )

    @api.model
    def _read_group_states(self, records, groups):
        """
        Returns a complete list of technical status keys to display all kanban columns.
        """
        return ["new", "active", "blocked"]

    @api.depends("debt_ledger_ids.amount", "debt_ledger_ids.direction")
    def _compute_current_debt(self):
        """
        Calculates the real-time debt balance based strictly on ledger entry logs.
        Triggers instantly when a new payment or debt row is inserted.
        """
        for card in self:
            debt_sum = 0.0
            for entry in card.debt_ledger_ids:
                if entry.direction == "increase":
                    debt_sum += entry.amount
                elif entry.direction == "decrease":
                    debt_sum -= entry.amount
            card.current_debt = debt_sum

    @api.depends("order_ids.amount_total", "order_ids.state")
    def _compute_sales_volume(self):
        """
        Packs total turnover directly from memory-resident Recordset.
        """
        for card in self:
            card.total_sales_volume = sum(
                order.amount_total for order in card.order_ids if order.state == "done"
            )

    @api.depends("total_sales_volume")
    def _compute_card_state(self):
        """
        Automatically shifts state between New and Active based on turnover metrics.
        Protects the 'blocked' status from being overwritten by financial recalculations.
        """
        for card in self:
            if card.state == "blocked":
                continue
            if card.total_sales_volume > 0.0:
                card.state = "active"
            else:
                card.state = "new"

    def _inverse_card_state(self):
        """
        Triggered when dragging on a kanban. Clears the ORM cache to capture the forced selected status.
        """
        pass

    @api.constrains("credit_limit")
    def _check_company_credit_limit(self):
        """
        Validates that the assigned card credit limit does not exceed the highest
        financial directive defined at the res.company level.
        """
        for card in self:
            company_limit = self.env.company.max_global_credit_limit
            if card.credit_limit > company_limit:
                raise ValidationError(
                    _(
                        "Configuration Error! Assigned credit limit (%s) cannot exceed "
                        "the global maximum allowed credit limit defined by company settings (%s)."
                    )
                    % (card.credit_limit, company_limit)
                )

    def write(self, vals):
        """
        Overrides core system write method to act as a rigorous transactional trigger.
        Blocks manual state mutations to 'active' without turnover or to 'blocked' with outstanding debt.
        """
        if "state" in vals:
            target_state = vals.get("state")

            if target_state == "new":
                for card in self:
                    if card.total_sales_volume > 0.0:
                        raise ValidationError(
                            _(
                                "Action Denied! Cannot reset loyalty card '%s' to 'New Card' status "
                                "because it already has an active sales volume of %s."
                            )
                            % (card.name, card.total_sales_volume)
                        )

            if target_state == "active":
                for card in self:
                    if card.total_sales_volume <= 0.0:
                        raise ValidationError(
                            _(
                                "Action Denied! Cannot manually activate card '%s' because its total sales volume is 0.00 UAH. "
                                "Activation occurs automatically upon the first completed sale transaction."
                            )
                            % card.name
                        )

            if target_state == "blocked":
                for card in self:
                    if card.current_debt > 0.0:
                        raise ValidationError(
                            _(
                                "Action Denied! Cannot block loyalty card '%s' because it has "
                                "an active outstanding debt of %s. Please clear the debt via the checkout wizard first."
                            )
                            % (card.name, card.current_debt)
                        )

        return super(BmLoyaltyCard, self).write(vals)
