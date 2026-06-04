from odoo import models, fields


class ResCompany(models.Model):
    """
    Inherits standard company model to define global maximum credit cap constraints.
    """

    _inherit = "res.company"

    max_global_credit_limit = fields.Float(
        string="Max Global Credit Limit",
        default=50000.0,
        help="The maximum credit limit that can be assigned to any loyalty card.",
    )
