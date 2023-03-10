# Copyright (c) 2013-2022, bnovate, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import textwrap
import itertools
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(filters)
    
    return columns, data, None, chart

def get_columns():
    return [
        # {'fieldname': 'weeknum', 'fieldtype': 'Data', 'label': _('Week'), 'width': 80},
        {'fieldname': 'name', 'fieldtype': 'Link', 'label': _('Sales Order'), 'options': 'Sales Order', 'width': 100},
        {'fieldname': 'customer', 'fieldtype': 'Link', 'label': _('Customer'), 'options': 'Customer', 'width': 80},
        {'fieldname': 'customer_name', 'fieldtype': 'Data', 'label': _('Customer Name'), 'width': 150},
        {'fieldname': 'currency', 'fieldtype': 'Data', 'label': _('Currency'), 'width': 70},
        {'fieldname': 'so_date', 'fieldtype': 'Date', 'label': _('SO date'), 'width': 80},
        {'fieldname': 'ship_date', 'fieldtype': 'Date', 'label': _('Ship date'), 'width': 80},
        # {'fieldname': 'qty', 'fieldtype': 'Int', 'label': _('Qty Ordered'), 'width': 100}, 
        {'fieldname': 'remaining_qty', 'fieldtype': 'Int', 'label': _('Qty to Deliver'), 'width': 100}, 
        {'fieldname': 'item_code', 'fieldtype': 'Link', 'label': _('Item code'), 'options': 'Item', 'width': 300, 'align': 'left'},
        # {'fieldname': 'item_name', 'fieldtype': 'Data', 'label': _('Item name'), 'width': 300},
        {'fieldname': 'item_group', 'fieldtype': 'Link', 'label': _('Item group'), 'options': 'Item Group', 'width': 150},
        {'fieldname': 'qty', 'fieldtype': 'Int', 'label': _('Qty'), 'width': 100},
        {'fieldname': 'delivered_qty', 'fieldtype': 'Int', 'label': _('Qty Delivered'), 'width': 100}, 
        {'fieldname': 'to_deliver_qty', 'fieldtype': 'Int', 'label': _('Qty to Deliver'), 'width': 100},
        {'fieldname': 'unit_price', 'fieldtype': 'Currency', 'label': _('Unit Price'), 'width': 100},
        {'fieldname': 'planned_income', 'fieldtype': 'Currency', 'label': _('Total Expected Revenue'), 'width': 150},
        {'fieldname': 'billed_income', 'fieldtype': 'Currency', 'label': _('Billed'), 'width': 100},
        {'fieldname': 'to_bill_income', 'fieldtype': 'Currency', 'label': _('Expected Billing'), 'width': 100},


    ]
    
def get_data(filters):
        
    group_filter = ""
    if filters.item_group:
        group_filter = "AND i.item_group = '{}'".format(filters.item_group)
        
    sql_query = """
SELECT
    so.name,
    so.customer,
    so.customer_name,
    so.currency,
    so.transaction_date as so_date,
    soi.delivery_date as ship_date,
    soi.item_code,
    i.item_name,
    i.item_group,
    soi.qty,
    soi.delivered_qty,
    (soi.qty - soi.delivered_qty) as to_deliver_qty,
    soi.base_net_rate as unit_price,
    soi.base_net_amount as planned_income,
    (soi.billed_amt / soi.net_amount) * soi.base_net_amount as billed_income, -- work around to get in base currency rather than invoice currency
    (soi.net_amount - soi.billed_amt) / soi.net_amount * soi.base_net_amount as to_bill_income
FROM `tabSales Order Item` AS soi
    JOIN `tabSales Order` AS so ON soi.parent = so.name
    JOIN `tabItem` AS i ON soi.item_code = i.name
WHERE so.docstatus = 1
    AND soi.delivery_date BETWEEN "{from_date}" AND "{to_date}"
    {group_filter}
ORDER BY soi.delivery_date DESC
    """.format(from_date=filters.from_date, to_date=filters.to_date, group_filter=group_filter)

    data = frappe.db.sql(sql_query, as_dict=True)
    return data


def get_chart(filters):
    
    group_filter = ""
    if filters.item_group:
        group_filter = """AND i.item_group = '{}'""".format(filters.item_group)
    
    # Assume monthly aggregation by default
    period = 'month'
    time_period_col = """DATE_FORMAT(soi.delivery_date, '%Y-%m') as time_period"""
    time_agg = ", MONTH(soi.delivery_date)"
    if filters.period_length and filters.period_length == 'quarter':
        period = 'quarter'
        time_period_col = """CONCAT(YEAR(soi.delivery_date), "-Q", QUARTER(soi.delivery_date)) as time_period"""
        time_agg = """, QUARTER(soi.delivery_date)"""
    elif filters.period_length and filters.period_length == 'year':
        period = 'year'
        time_period_col = """YEAR(soi.delivery_date) as time_period"""
        time_agg = ""
        
    sql_query = """
SELECT
    {time_period_col},
    SUM(soi.qty) as qty,
    SUM(soi.delivered_qty) as delivered_qty,
    SUM(soi.qty - soi.delivered_qty) as to_deliver_qty,
    SUM(soi.base_net_amount) as expected_income,
    SUM((soi.billed_amt / soi.net_amount) * soi.base_net_amount) as billed, -- work around to get in base currency rather than invoice currency
    SUM((soi.net_amount - soi.billed_amt) / soi.net_amount * soi.base_net_amount) as to_bill
FROM `tabSales Order Item` AS soi
    JOIN `tabSales Order` AS so ON soi.parent = so.name
    JOIN `tabItem` AS i ON soi.item_code = i.name
WHERE so.docstatus = 1
    AND soi.delivery_date BETWEEN "{from_date}" AND "{to_date}"
    {group_filter}
GROUP BY YEAR(soi.delivery_date) {time_agg}
ORDER BY soi.delivery_date ASC
    """.format(from_date=filters.from_date, to_date=filters.to_date, group_filter=group_filter, time_period_col=time_period_col, time_agg=time_agg)
    
    data = frappe.db.sql(sql_query, as_dict=True)
    
    # Build dict of arrays, that store the sum of items in each group, each week.
    
    to_do_key, done_key, total_key = 'to_bill', 'billed', 'expected_income'
    title = "Expected revenue per {period} [CHF]. *Based on expected shipping date*.".format(period=period)
    if filters.sum_type and filters.sum_type == 'qty':
        to_do_key, done_key, total_key = 'to_deliver_qty', 'delivered_qty', 'qty'
        title = "Expected deliveries per {period} [units]. *Based on expected shipping date*.".format(period=period)
        
    periods = [it['time_period'] for it in data]
    to_do = [safe_round(it[to_do_key]) for it in data]
    done = [safe_round(it[done_key]) for it in data]
    total = [safe_round(it[total_key]) for it in data]
    
    chart = {
        "data": {
            "labels": periods,
            "datasets": [{
                "name": "Billed",
                "values": done,
                "chartType": "bar",
            }, {
                "name": "Expected",
                "values": to_do,
                "chartType": "bar",
            }, {
                "name": "Total",
                "values": total,
                "chartType": "line",
            }],
        },
        # "colors": ["purple", "#ffa3ef", "light-blue"],
        "type": 'axis-mixed',
        "barOptions": {
            "stacked": True,
            "spaceRatio": 0.1,
        },
        # "axisOptions": {
        #    "xIsSeries": "True"
        #},
        "title": title,
    }
    return chart
    
    
### Helpers

def safe_round(x):
    return 0 if x is None else round(x, 2)

def ellipsis(text, length=10):
    if len(text) <= length:
        return text
    return text[:int(length/2)-1] + "…" + text[-int(length/2):]
