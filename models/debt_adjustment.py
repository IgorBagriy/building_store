# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class BmDebtAdjustment(models.Model):
    """
    Official audit document for manual opening balances input and debt adjustments.
    """

    _name = "bm.debt.adjustment"
    _description = "Debt Adjustment Document"
    _order = "adjustment_date desc, id desc"

    name = fields.Char(
        string="Document Number",
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: "/",
    )

    adjustment_date = fields.Date(
        string="Adjustment Date",
        required=True,
        index=True,
        default=fields.Date.context_today,
    )

    partner_id = fields.Many2one(
        "res.partner", string="Master (Customer)", required=True, index=True
    )

    card_id = fields.Many2one(
        "bm.loyalty.card",
        string="Target Loyalty Card",
        compute="_compute_card_id",
        store=True,
        readonly=False,
        ondelete="restrict",
        index=True,
    )

    amount = fields.Float(
        string="Adjustment Amount",
        required=True,
        digits=(16, 2),
    )

    type = fields.Selection(
        [("increase", "Increase Debt (+)"), ("decrease", "Decrease Debt (-)")],
        string="Adjustment Type",
        required=True,
        default="decrease",
        index=True,
    )

    user_id = fields.Many2one(
        "res.users",
        string="Author (Administrator)",
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
    )

    @api.depends("partner_id")
    def _compute_card_id(self):
        """
        Automatically links the loyalty card associated with the selected partner.
        Prioritizes active cards with outstanding debt balance.
        """
        for order in self:
            if order.partner_id:
                # Look for an unblocked loyalty card associated with the partner that already has an active debt balance
                card = self.env["bm.loyalty.card"].search(
                    [
                        ("partner_id", "=", order.partner_id.id),
                        ("state", "!=", "blocked"),
                        ("current_debt", ">", 0.0),
                    ],
                    limit=1,
                )

                order.card_id = card
            else:
                order.card_id = False

    @api.onchange("card_id", "type")
    def _onchange_card_id(self):
        """
        Instantly autofills the adjustment amount with the card's current outstanding debt
        only when the transaction type is set to 'decrease' (repayment).
        """
        for record in self:
            if record.type == "decrease" and record.card_id:
                record.amount = record.card_id.current_debt
            elif record.type == "increase" and not record.amount:
                record.amount = 0.0

    def unlink(self):
        """
        Cascade cleans associated transaction sub-ledger lines before dropping the document.
        """
        if self.env.context.get("install_mode") or self.env.context.get(
            "module_uninstall"
        ):
            return super(BmDebtAdjustment, self).unlink()

        # Call centralized ledger clean service to maintain structural data consistency
        self.env["bm.debt.ledger"]._clean_document_movements(self._name, self.ids)
        return super(BmDebtAdjustment, self).unlink()

    @api.model_create_multi
    def create(self, vals_list):
        """
        Overrides default create behavior to assign strict sequential unique audit numbering
        and instantly post transaction movements into the unmodifiable sub-ledger.
        """
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("bm.debt.adjustment.seq")
                    or "/"
                )

        records = super(BmDebtAdjustment, self).create(vals_list)

        ledger_vals_list = []
        cards_to_recompute = self.env["bm.loyalty.card"]

        for record in records:
            if record.amount <= 0.0:
                raise ValidationError(
                    _(
                        "Validation Error! The adjustment amount value must be strictly greater than zero."
                    )
                )

            if record.type == "decrease":
                current_card_debt = record.card_id.current_debt
                if record.amount > current_card_debt:
                    raise ValidationError(
                        _(
                            "Financial Violation! The repayment amount (%s) cannot exceed "
                            "the actual outstanding debt balance on this card (%s)."
                        )
                        % (record.amount, current_card_debt)
                    )

            ledger_vals_list.append(
                {
                    "partner_id": record.partner_id.id,
                    "card_id": record.card_id.id,
                    "amount": record.amount,
                    "direction": record.type,
                    "res_model": record._name,
                    "res_id": record.id,
                }
            )
            cards_to_recompute |= record.card_id

        if ledger_vals_list:
            self.env["bm.debt.ledger"].create(ledger_vals_list)

        if cards_to_recompute:
            cards_to_recompute._compute_current_debt()

        return records
