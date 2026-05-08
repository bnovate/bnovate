# Copyright (c) 2013, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, getdate, add_months, add_years
from erpnext import get_company_currency

from bnovate.bnovate.report.revenue_analytics_master.revenue_analytics_master import get_data as get_master_data , validate_filters


def execute(filters=None):
    if not filters:
        filters = {}

    validate_filters(filters)

    columns = get_columns(filters)
    data = get_data(filters)

    return columns, data

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

    aggregated_data = get_master_data(filters)

    # Aggregate 
    amounts = {}
    for row in aggregated_data:
        key = (row.revenue_stream_name, row.get("month"))
        if key not in amounts:
            amounts[key] = 0

        amounts[key] += row.amount
            

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
