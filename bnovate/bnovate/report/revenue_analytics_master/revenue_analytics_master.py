# Copyright (c) 2013, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

from frappe import _
from frappe.utils import flt, getdate, add_months
from erpnext import get_company_currency

 
def execute(filters=None):
    if not filters:
        filters = {}

    validate_filters(filters)

    columns = get_columns(filters)
    data = get_data(filters)

    return columns, data

def validate_filters(filters):
    from_date = getdate(filters.get("from_date"))
    to_date = getdate(filters.get("to_date"))

    if from_date > to_date:
        frappe.throw(_("From Date must be before To Date"))


def get_columns(filters):
    return [{
        "fieldname": "stage",
        "label": _("Stage"),
        "fieldtype": "Data",
        "width": 150
    }, 
    {
        "fieldname": "revenue_stream_name",
        "label": _("Revenue Stream"),
        "fieldtype": "Data",
        "width": 200
    },
    {
        "fieldname": "item_group",
        "label": _("Item Group"),
        "fieldtype": "Data",
        "width": 200
    },
    {
        "fieldname": "item_code",
        "label": _("Item Code"),
        "fieldtype": "Link",
        "width": 200,
        "options": "Item"
    },
    {
        "fieldname": "posting_date",
        "label": _("Posting Date"),
        "fieldtype": "Date",
        "width": 150
    },
    {
        "fieldname": "month",
        "label": _("Month"),
        "fieldtype": "Data",
        "width": 150
    },
    {
        "fieldname": "amount",
        "label": _("Amount"),
        "fieldtype": "Currency",
        "width": 150
    },
    {
        "fieldname": "so_name",
        "label": _("Sales Order"),
        "fieldtype": "Link",
        "options": "Sales Order",
        "width": 200
    },
    {
        "fieldname": "sinv_name",
        "label": _("Sales Invoice"),
        "fieldtype": "Link",
        "options": "Sales Invoice",
        "width": 200
    }]

def get_data(filters):
    filters.include_sinv = filters.get("include") in ("All", "Billed")
    filters.include_so = filters.get("include") in ("All", "Unbilled")

    filters.where_conditions = "WHERE true"    
    if filters.revenue_stream:
        filters.where_conditions += " AND IFNULL(rs.name, 'Other') = '{revenue_stream}' ".format(**filters)


    # TODO: add shipping, separate from VAT.

    data_query = """
        WITH orders AS (
            SELECT
                sii.item_code,
                si.posting_date as posting_date,
                DATE_FORMAT(si.posting_date, '%Y-%m') as month,
                sii.base_net_amount as amount,
                sii.sales_order as so_name,
                si.name as sinv_name,
                "Billed" as stage
            FROM `tabSales Invoice` si
            JOIN `tabSales Invoice Item` sii ON sii.parent = si.name 
            WHERE si.docstatus = 1
                AND si.company = '{company}'
                AND si.posting_date BETWEEN '{from_date}' AND '{to_date}'
                AND {include_sinv}

            UNION ALL

            SELECT
                soi.item_code,
                soi.delivery_date as posting_date,
                DATE_FORMAT(soi.delivery_date, '%Y-%m') as month,
                (soi.net_amount - ifnull(soi.billed_amt, 0)) * so.conversion_rate AS amount,  -- Unbilled amount in company currency
                so.name as so_name,
                NULL as sinv_name,
                "Unbilled" as stage
            FROM `tabSales Order` so
            JOIN `tabSales Order Item` soi ON soi.parent = so.name 
            WHERE so.docstatus = 1
                AND so.status != 'Closed'
                AND so.company = '{company}'
                AND so.delivery_date BETWEEN '{from_date}' AND '{to_date}'
                AND(soi.net_amount - ifnull(soi.billed_amt, 0)) > 0
                AND {include_so}
        )

        SELECT
            o.stage,
            IFNULL(rs.name, 'Other') as revenue_stream_name,
            ig.name as item_group,
            o.item_code,
            i.item_name,
            o.posting_date,
            o.month,
            o.amount,
            o.so_name,
            o.sinv_name
        FROM orders o
        JOIN `tabItem` i on i.item_code = o.item_code
        JOIN `tabItem Group` ig ON ig.name = i.item_group
        LEFT JOIN `tabRevenue Stream` rs ON rs.name = ig.revenue_stream
        {where_conditions}
    """.format(**filters)
    
    aggregated_data = frappe.db.sql(data_query, as_dict=True)

    return aggregated_data