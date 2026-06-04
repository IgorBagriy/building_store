{
    "name": "Building Store Management",
    "version": "19.0.1.0.0",
    "category": "Sales/Retail",
    "summary": "Comprehensive ERP core for construction materials retail and trade operations.",
    "description": """
        Building Store Management System
        ================================
        Professional architectural core module for automated sales processing, 
        loyalty program lifecycle, and customer debt ledger control.
    """,
    "author": "Igor Bagriy",
    "depends": [
        "base",
        "mail",
        "contacts",
    ],
    "data": [
        "security/security_groups.xml",
        "security/record_rules.xml",
        "security/ir.model.access.csv",
        "wizard/payment_wizard_views.xml",
        "views/res_company_views.xml",
        "views/store_product_views.xml",
        "views/store_order_views.xml",
        "views/debt_adjustment_views.xml",
        "views/loyalty_card_views.xml",
        "views/debt_ledger_views.xml",
        "report/report_actions.xml",
        "report/client_report_templates.xml",
        "views/menu_views.xml",
    ],
    "demo": [
        "data/demo_data.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
