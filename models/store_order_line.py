from odoo import api, models, fields


class BmOrderLine(models.Model):
    """
    Tabular section containing concrete items inside a specific sale order.
    """

    _name = "bm.order.line"
    _description = "Store Sale Order Line"

    order_id = fields.Many2one(
        "bm.order",
        string="Order Reference",
        required=True,
        ondelete="cascade",
        index=True,
    )

    product_id = fields.Many2one(
        "bm.product",
        string="Material (Product)",
        required=True,
        ondelete="restrict",
        index=True,
    )

    product_uom_qty = fields.Float(string="Quantity", required=True, default=1.0)

    price_unit = fields.Float(
        string="Unit Price", compute="_compute_price_unit", store=True, readonly=False
    )

    price_subtotal = fields.Float(
        string="Subtotal", compute="_compute_price_subtotal", store=True
    )

    @api.depends("product_id")
    def _compute_price_unit(self):
        """
        Dynamically fetches the standard retail price from the product template.
        """
        for line in self:
            if line.product_id:
                line.price_unit = line.product_id.list_price
            else:
                line.price_unit = 0.0

    @api.depends("product_uom_qty", "price_unit")
    def _compute_price_subtotal(self):
        """
        Computes row line values as a simple flat equation without procedural looping.
        """
        for line in self:
            line.price_subtotal = line.product_uom_qty * line.price_unit
