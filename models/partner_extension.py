from odoo import models, fields


class ResPartner(models.Model):
    """
    Inherits standard Odoo partner model to add global single cashback wallet.
    """

    _inherit = "res.partner"

    loyalty_card_ids = fields.One2many(
        "bm.loyalty.card", "partner_id", string="Loyalty Cards"
    )

    total_cashback_balance = fields.Float(
        string="Total Cashback Balance",
        readonly=True,
        copy=False,
        help="The single unified balance of accumulated marketing cashback available for redemption at checkouts.",
    )
