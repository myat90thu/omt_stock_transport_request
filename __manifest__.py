{
    "name": "Stock Transport Order Request",
    "version": "1.0.0",
    "summary": "Stock Transport Order Request with dynamic approval rules (Odoo 19)",
    "category": "Warehouse",
    "author": "Your Company",
    "license": "LGPL-3",
    "depends": ["stock", "product"],
    "data": [
        "data/sto_sequence.xml",
        "security/ir.model.access.csv",
        "views/sto_request_views.xml",
        "views/sto_approval_rule_views.xml"
    ],
    "installable": True,
    "application": False
}