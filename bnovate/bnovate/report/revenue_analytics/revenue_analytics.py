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
    columns = [
        {
            "fieldname": "revenue_stream_name",
            "label": _("Revenue Stream"),
            "fieldtype": "Data",
            "width": 200
        }
    ]

    from_date = getdate(filters.get("from_date"))
    to_date = getdate(filters.get("to_date"))

    current = from_date
    while current <= to_date:
        month_year = current.strftime("%b %Y")
        fieldname = current.strftime("%Y-%m")
        columns.append({
            "fieldname": fieldname,
            "label": month_year,
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120
        })
        current = add_months(current, 1)

    columns.append({
        "fieldname": "total",
        "label": _("Total"),
        "fieldtype": "Currency",
        "options": "currency",
        "width": 120
    })

    return columns

def get_data(filters):
    currency = get_company_currency(filters.get("company"))
    filters.include_sinv = filters.get("include") in ("All", "Billed")
    filters.include_so = filters.get("include") in ("All", "Unbilled")

    # Get all revenue streams in tree order
    revenue_streams = frappe.db.sql("""
        SELECT 
            rs.name, 
            rs.revenue_stream_name, 
            rs.lft, 
            rs.rgt, 
            rs.is_group, 
            rs.parent_revenue_stream,
            COUNT(rs_parents.name) as depth
        FROM `tabRevenue Stream` rs
        LEFT OUTER JOIN `tabRevenue Stream` rs_parents ON rs_parents.lft < rs.lft AND rs_parents.rgt > rs.rgt
        GROUP BY rs.name
        ORDER BY rs.lft
    """, as_dict=True)

    # Get aggregated data
    data_query = """
        WITH orders AS (
            SELECT
                sii.item_code,
                DATE_FORMAT(si.posting_date, '%%Y-%%m') as month,
                sii.base_net_amount as amount,
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
                DATE_FORMAT(so.delivery_date, '%%Y-%%m') as month,
                (soi.net_amount - ifnull(soi.billed_amt, 0)) * so.conversion_rate AS amount,  -- Unbilled amount in company currency
                "Unbilled" as stage
            FROM `tabSales Order` so
            JOIN `tabSales Order Item` soi ON soi.parent = so.name 
            WHERE so.docstatus = 1
                AND so.status != 'Closed'
                AND so.company = '{company}'
                AND so.delivery_date BETWEEN '{from_date}' AND '{to_date}'
                AND {include_so}
        )

        SELECT
            rs.name as revenue_stream_name,
            rs.parent_revenue_stream,
            month,
            SUM(o.amount) as amount
        FROM orders o
        JOIN `tabItem` i on i.item_code = o.item_code
        JOIN `tabItem Group` ig ON ig.name = i.item_group
        JOIN `tabRevenue Stream` rs ON rs.name = ig.revenue_stream
        GROUP BY rs.name, month

    """.format(**filters)

    aggregated_data = frappe.db.sql(data_query, filters, as_dict=True)

    # Create a dict for quick lookup
    amounts = {}
    for row in aggregated_data:
        key = (row.revenue_stream_name, row.month)
        amounts[key] = flt(row.amount)

    # Build the data rows with initial values
    data = []
    rows_by_name = {}
    from_date = getdate(filters.get("from_date"))
    to_date = getdate(filters.get("to_date"))

    for rs in revenue_streams:
        row = {
            "name": rs.name,
            "revenue_stream_name": rs.revenue_stream_name,
            "parent_revenue_stream": rs.parent_revenue_stream,
            "indent": rs.depth
        }

        total = 0
        current = from_date
        while current <= to_date:
            month_key = current.strftime("%Y-%m")
            amount = amounts.get((rs.name, month_key), 0)
            row[month_key] = amount
            total += amount
            current = add_months(current, 1)

        row["total"] = total
        data.append(row)
        rows_by_name[rs.name] = row

    # Rollup child amounts into parent revenue streams
    for rs in reversed(revenue_streams):
        if not rs.parent_revenue_stream:
            continue
        child_row = rows_by_name.get(rs.name)
        parent_row = rows_by_name.get(rs.parent_revenue_stream)
        if not child_row or not parent_row:
            continue

        current = from_date
        while current <= to_date:
            month_key = current.strftime("%Y-%m")
            parent_row[month_key] = parent_row.get(month_key, 0) + child_row.get(month_key, 0)
            current = add_months(current, 1)

        parent_row["total"] = parent_row.get("total", 0) + child_row.get("total", 0)

    return data
