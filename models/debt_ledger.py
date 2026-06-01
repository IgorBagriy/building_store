# -*- coding: utf-8 -*-
from odoo import api, models, fields


class BmDebtLedger(models.Model):
    """
    Transactional financial ledger tracking individual modifications of balances.
    """

    _name = "bm.debt.ledger"
    _description = "Customer Debt Transaction Ledger"
    _order = "date desc, id desc"

    date = fields.Datetime(
        string="Transaction Date",
        required=True,
        readonly=True,
        index=True,
        default=fields.Datetime.now,
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Master (Customer)",
        required=True,
        readonly=True,
        ondelete="restrict",
        index=True,
    )

    card_id = fields.Many2one(
        "bm.loyalty.card",
        string="Loyalty Card",
        required=True,
        readonly=True,
        ondelete="restrict",
        index=True,
    )

    amount = fields.Float(
        string="Transaction Amount", required=True, readonly=True, digits=(16, 2)
    )

    direction = fields.Selection(
        [("increase", "Increase Debt (+)"), ("decrease", "Decrease Debt (-)")],
        string="Direction",
        required=True,
        readonly=True,
        index=True,
    )

    res_model = fields.Char(
        string="Origin Document Type", required=True, readonly=True, index=True
    )

    res_id = fields.Integer(
        string="Origin Document ID", required=True, readonly=True, index=True
    )

    @api.model
    def _clean_document_movements(self, res_model, res_ids):
        """
        Called automatically when any documents are deleted.
        """
        lines = self.search([("res_model", "=", res_model), ("res_id", "in", res_ids)])
        if lines:
            lines.unlink()

    def unlink(self):
        """
        Universal trigger: recalculates card debt when movement is removed.
        """
        cards = self.mapped("card_id")
        res = super(BmDebtLedger, self).unlink()
        if cards:
            # Forcibly update the balance in the database
            cards._compute_current_debt()
        return res
