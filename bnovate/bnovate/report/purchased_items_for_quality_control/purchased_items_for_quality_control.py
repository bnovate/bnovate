# Copyright (c) 202666666vate, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    
    return columns, data

def get_columns():
    return [
        {
            "label": _("Posting Date"),
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "label": _("Purchase Order"),
            "fieldname": "purchase_order",
            "fieldtype": "Link",
            "options": "Purchase Order",
            "width": 160,
        },
        {
            "label": _("Supplier"),
            "fieldname": "supplier",
            "fieldtype": "Link",
            "options": "Supplier",
            "width": 160,
        },
        {
            "label": _("Supplier Name"),
            "fieldname": "supplier_name",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": _("Item Code"),
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 120,
        },
        {
            "label": _("Item Name"),
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 220,
        },
        {
            "label": _("Qty"),
            "fieldname": "qty",
            "fieldtype": "Float",
            "width": 90,
        },
    ]
      
    
def get_data(filters):

    sql_query = """
SELECT 
	pr.posting_date as posting_date,
    po.name as purchase_order,
    po.supplier,
    s.supplier_name as supplier_name,
    pri.item_code, 
    pri.item_name,
    pri.qty
FROM `tabPurchase Receipt Item` as pri
	JOIN `tabItem` as it ON pri.item_code = it.name
	JOIN `tabPurchase Receipt` as pr ON pri.parent = pr.name
	JOIN `tabPurchase Order` as po ON pri.purchase_order = po.name
	JOIN `tabSupplier` as s ON po.supplier = s.name
WHERE pri.docstatus = 0
	AND it.qc_required = 1
ORDER BY pr.posting_date
    ;
    """.format()

    data = frappe.db.sql(sql_query, as_dict=True)
    return data
