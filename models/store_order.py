from odoo import api, models, fields


class BmOrder(models.Model):
    """
    Main document journal for capturing customer sale transactions.
    """

    _name = "bm.order"
    _description = "Store Sale Order"
    _order = "date_order desc, id desc"

    name = fields.Char(
        string="Order Number",
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: "/",
    )

    date_order = fields.Datetime(
        string="Order Date",
        required=True,
        readonly=True,
        index=True,
        default=fields.Datetime.now,
    )

    partner_id = fields.Many2one(
        "res.partner", string="Customer", required=True, ondelete="restrict", index=True
    )

    card_id = fields.Many2one(
        "bm.loyalty.card",
        string="Loyalty Card",
        compute="_compute_card_id",
        store=True,
        readonly=False,
        ondelete="restrict",
        index=True,
    )

    user_id = fields.Many2one(
        "res.users",
        string="Cashier",
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
    )

    order_line_ids = fields.One2many(
        "bm.order.line", "order_id", string="Order Lines", copy=True
    )

    amount_untaxed = fields.Float(
        string="Untaxed Amount",
        compute="_compute_order_totals",
        store=True,
        help="The raw sum of all order lines before applying any discounts.",
    )

    discount_percent = fields.Float(
        string="Discount (%)", compute="_compute_discount_percent", store=True
    )

    discount_amount = fields.Float(
        string="Discount Amount", compute="_compute_order_totals", store=True
    )

    amount_total = fields.Float(
        string="Total to Pay", compute="_compute_order_totals", store=True, index=True
    )

    state = fields.Selection(
        [("draft", "Draft Check"), ("done", "Completed Sale")],
        string="Status",
        default="draft",
        required=True,
        copy=False,
        index=True,
    )

    @api.depends("partner_id")
    def _compute_card_id(self):
        """
        Automatically links the loyalty card associated with the selected partner.
        Allows 'new' and 'active' cards, but strictly filters out 'blocked' ones.
        """
        for order in self:
            if order.partner_id:
                order.card_id = self.env["bm.loyalty.card"].search(
                    [
                        ("partner_id", "=", order.partner_id.id),
                        ("state", "!=", "blocked"),
                    ],
                    limit=1,
                )
            else:
                order.card_id = False

    @api.depends("card_id")
    def _compute_discount_percent(self):
        """
        Fetches the current discount percentage upon card selection.
        """
        for order in self:
            if order.card_id and order.card_id.state in ["new", "active"]:
                order.discount_percent = order.card_id.discount_percent
            else:
                order.discount_percent = 0.0

    @api.depends("order_line_ids.price_subtotal", "discount_percent")
    def _compute_order_totals(self):
        """
        Optimized calculation of order financial summaries using flat dependencies.
        Evaluates raw lines, applies card discount rules, and determines net total.
        """
        for order in self:
            raw_sum = sum(line.price_subtotal for line in order.order_line_ids)
            order.amount_untaxed = raw_sum
            disc_val = raw_sum * (order.discount_percent / 100.0)
            order.discount_amount = disc_val
            order.amount_total = raw_sum - disc_val

    def unlink(self):
        self.env["bm.debt.ledger"]._clean_document_movements(self._name, self.ids)
        return super().unlink()

    @api.model_create_multi
    def create(self, vals_list):
        """
        Overrides system create method to inject sequential human-readable numbering.
        """
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("bm.order.seq") or "/"
                )
        return super().create(vals_list)
