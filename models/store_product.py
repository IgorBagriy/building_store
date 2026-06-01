# -*- coding: utf-8 -*-
from odoo import models, fields


class BmProduct(models.Model):
    """
    Manages custom database table for construction products nomenclature.
    """

    _name = "bm.product"
    _description = "Construction Store Product"
    _order = "name, sku"

    name = fields.Char(string="Product Name", required=True, index=True, translate=True)

    sku = fields.Char(string="SKU / Article", required=True, copy=False, index=True)

    list_price = fields.Float(string="Retail Price", required=True)

    _unique_sku = models.Constraint(
        "unique(sku)",
        "The SKU/Article code must be absolutely unique across the inventory!",
    )
