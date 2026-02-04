{
    "name": "Stock Transport Order Request",
    "version": "2.0.0",
    "summary": "Stock Transport Order Request with dynamic approval rules (Odoo 19)",
    "category": "Warehouse",
    "author": "Max Thu - Odoo Myanmar Tutorial",
    "license": "LGPL-3",
    "depends": ["stock", "product"],
    "data": [
        "data/sto_sequence.xml",
        "security/ir.model.access.csv",
        "views/sto_request_views.xml",
        "views/sto_approval_rule_views.xml",
        "views/stock_warehouse_views.xml"
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False
}