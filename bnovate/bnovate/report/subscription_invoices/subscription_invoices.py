# Copyright (c) 2023, bNovate, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

def execute(filters=None):
    return get_columns(), get_data(filters)

def get_columns():
    return [
        {'fieldname': 'customer', 'label': _('Customer'), 'fieldtype': 'Link', 'options': 'Customer', 'width': 100},
        {'fieldname': 'customer_name', 'label': _('Customer name'), 'fieldtype': 'Data', 'width': 150},
        {'fieldname': 'subscription', 'label': _('Subscription'), 'fieldtype': 'Link', 'options': 'Subscription Contract', 'width': 100},
        {'fieldname': 'posting_date', 'label': _('Posting Date'), 'fieldtype': 'Date', 'width': 100},
        {'fieldname': 'sales_invoice', 'label': _('Invoice'), 'fieldtype': 'Link', 'options': 'Sales Invoice', 'width': 100},
        # {'fieldname': 'docstatus', 'label': _('Status'), 'fieldtype': 'Data', 'width': 100},
        {'fieldname': 'status', 'label': _('Status'), 'fieldtype': 'Data', 'width': 100},
    ]


def get_data(filters):
    subscription = filters.subscription if filters.subscription else "%"
    customer = filters.customer if filters.customer else "%" 
    sql_query = """
    SELECT
        sii.subscription,
        -- ss.name AS subscription,
        ss.customer,
        c.customer_name AS customer_name,
        si.posting_date AS posting_date,
        si.name AS sales_invoice,
        si.docstatus AS docstatus,
        si.status AS status
    FROM `tabSales Invoice Item` sii
        JOIN `tabSales Invoice` si ON sii.parent = si.name
        JOIN `tabSubscription Contract` ss ON ss.name = sii.subscription
        JOIN `tabCustomer` c on ss.customer = c.name
    WHERE ss.name LIKE "{subscription}"
        AND ss.customer LIKE "{customer}"
    ORDER BY ss.customer, ss.name, si.posting_date
    """.format(subscription = subscription, customer=customer)

    entries = frappe.db.sql(sql_query, as_dict=True)
    return entries