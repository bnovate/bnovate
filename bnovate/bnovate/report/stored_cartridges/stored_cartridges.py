# Copyright (c) 2023, bnovate, libracore and contributors
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
        {'fieldname': 'serial_no', 'fieldtype': 'Link', 'label': _('Serial No'), 'options': 'Serial No', 'width': 100},
        {'fieldname': 'type', 'fieldtype': 'Data', 'label': _('Type'), 'width': 150}, 
        {'fieldname': 'item_code', 'fieldtype': 'Link', 'label': _('Item'), 'options': 'Item', 'width': 100},
        {'fieldname': 'warehouse', 'fieldtype': 'Link', 'label': _('Warehouse'), 'options': 'Warehouse', 'width': 100},
        {'fieldname': 'purchase_document_no', 'fieldtype': 'Link', 'label': _('Transfer doc'), 'options': 'Stock Entry', 'width': 100}, 
        {'fieldname': 'purchase_date', 'fieldtype': 'Date', 'label': _('Since date'), 'width': 80},
        {'fieldname': 'from_customer', 'fieldtype': 'Link', 'label': _('Last Customer'), 'options': 'Customer', 'width': 120},
        {'fieldname': 'customer_name', 'fieldtype': 'Data', 'label': _('Last Customer Name'), 'width': 300, 'align': 'left'}, 
    ]
    
def get_data(filters):
    extra_filters = ""
    if filters.customer:
        extra_filters += 'AND ste.from_customer = "{}"'.format(filters.customer)

    sql_query = """
        SELECT 
            sn.serial_no, 
            IF(sn.serial_no LIKE "%BNO%", "Rental", "Customer-owned") as type,
            sn.item_code, 
            sn.warehouse, 
            sn.purchase_document_type,
            sn.purchase_document_no,
            sn.purchase_date,
            ste.from_customer,
            cr.customer_name
        FROM `tabSerial No` sn
        JOIN `tabStock Entry` ste ON sn.purchase_document_no = ste.name
        LEFT JOIN `tabCustomer` cr ON ste.from_customer = cr.name
        WHERE sn.item_code = "100146"
            AND	sn.warehouse IN ("Repairs - bN", "To Refill - bN")
            {extra_filters}
        ORDER BY sn.serial_no
    """.format(extra_filters=extra_filters)

    data = frappe.db.sql(sql_query, as_dict=True)

    for row in data:
        if row['type'] == 'Rental' and row['customer_name']:
            row['type'] = '<span style="color: orangered">{}</span>'.format(row['type'])
            row['customer_name'] = '<span style="color: orangered">{}</span>'.format(row['customer_name'])
    
    return data
