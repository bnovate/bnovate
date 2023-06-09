# Copyright (c) 2013-2022, bnovate, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import textwrap
import itertools
from frappe import _

from bnovate.bnovate.report.projected_stock import projected_stock

from bnovate.bnovate.utils.enclosures import is_enclosure

def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    message = "Test message"
    chart = get_chart(filters)
    
    return columns, data, message, chart

def get_columns(filters):
    guaranteed_info = """
<p>Guaranteed stock before SO is fulfilled.</p>

<p align='left'>Calculation: 
<ul>
    <li>Current stock balance</li>
    <li>- items <b>consumed</b> by WO (at <i>start date</i>)</li>
    <li>- SO (at <i>ship date</i>)</li>
</ul>
</p>
"""

    projected_info = """
<p>Projected stock before SO is fulfilled.</p>

<p align='left'>Calculation: 
<ul>
    <li>Current stock balance</li>
    <li>- items <b>consumed</b> by WO (at <i>start date</i>)</li>
    <li>- SO (at <i>ship date</i>)</li>
    <li>+ PO (at <i>expected delivery date</i> or <i>Reqd by date</i>)</li>
    <li>+ items <b>produced</b> by WO (at <i>expected delivery date</i> if it exists, otherwise <i>start date</i>).</li>
</ul>
</p>
"""
    return [
        {'fieldtype': 'Data', 'label': '', 'width': 20},
        {'fieldname': 'sufficient_stock', 'fieldtype': 'Data', 'label': _('Go?'), 'width': 50, 'align': 'center'},
        {'fieldname': 'weeknum', 'fieldtype': 'Data', 'label': _('Week'), 'width': 80},
        {'fieldname': 'indicator', 'fieldtype': 'Data', 'label': _('Status'), 'width': 90},
        {'fieldname': 'sales_order', 'fieldtype': 'Link', 'label': _('Sales Order'), 'options': 'Sales Order', 'width': 90},
        {'fieldname': 'customer', 'fieldtype': 'Link', 'label': _('Customer'), 'options': 'Customer', 'width': 80, 'align': 'left'},
        {'fieldname': 'customer_name', 'fieldtype': 'Data', 'label': _('Customer Name'), 'width': 150, 'align': 'left'},
        {'fieldname': 'ship_date', 'fieldtype': 'Data', 'label': _('Ship date'), 'width': 80},
        # {'fieldname': 'qty', 'fieldtype': 'Int', 'label': _('Qty Ordered'), 'width': 100}, 
        {'fieldname': 'remaining_qty', 'fieldtype': 'Int', 'label': _('Qty to Deliver'), 'width': 100}, 
        {'fieldname': 'item_code', 'fieldtype': 'Link', 'label': _('Item code'), 'options': 'Item', 'width': 300, 'align': 'left'},
        {'fieldname': 'serial_nos', 'fieldtype': 'Data', 'label': _('Serial No'), 'width': 100, 'align': 'left'},
        # {'fieldname': 'item_name', 'fieldtype': 'Data', 'label': _('Item name'), 'width': 300},
        {'fieldname': 'item_group', 'fieldtype': 'Link', 'label': _('Item group'), 'options': 'Item Group', 'width': 150, 'align': 'left'},
        # {'fieldname': 'status', 'fieldtype': 'Data', 'label': _('Status'), 'width': 100}

        {'fieldname': 'projected_stock', 'fieldtype': 'Int', 
            'label': '<span data-html="true" data-toggle="tooltip" data-placement="bottom" data-container="body" title="{}">Proj. Stock <i class="fa fa-info-circle"></i></span>'.format(projected_info), 
            'width': 110},
        {'fieldname': 'guaranteed_stock', 'fieldtype': 'Int', 
            'label': '<span data-html="true" data-toggle="tooltip" data-placement="bottom" data-container="body" title="{}">Guar. Stock <i class="fa fa-info-circle"></i></span>'.format(guaranteed_info), 
            'width': 110},

        {'fieldname': 'work_order', 'fieldtype': 'Link', 'label': _('Work Order'), 'options': 'Work Order', 'width': 250, 'align': 'left'},
    ]
    
def get_data(filters):
    

    status_filter = " = 1 " # Only submitted
    if filters.include_drafts:
        status_filter = " <= 1" # include drafts and submitted.

    extra_filters = ""
    if filters.only_manufacturing:
        extra_filters += "AND it.include_item_in_manufacturing = 1"

    so_filter = ""
    if filters.sales_order:
        so_filter = "WHERE o.sales_order = '{}'".format(filters.sales_order)
    
    # Join projected stock with sales order items:
    projected_stock_query = projected_stock.build_query(filters.include_drafts, filters.include_drafts, None, None)
    sql_query = """
    WITH 
    p AS ( -- projected stock
        {projected_stock_query}
    ),

	o AS (( -- orders, union of SO items and SO packed items. The original "Orders to fulfill"
    SELECT
        0 AS indent,
        soi.name,
        soi.name as detail_docname,
        WEEK(soi.delivery_date) as weeknum,
        soi.parent as sales_order,
        so.customer as customer,
        so.customer_name as customer_name,
        soi.qty as qty,
        (soi.qty - soi.delivered_qty) AS remaining_qty,
        soi.delivery_date as delivery_date,
        soi.item_code as item_code,
        it.item_name as item_name,
        it.item_group as item_group,
        soi.serial_nos as serial_nos,
        FALSE as is_packed_item,
        soi.idx as idx,
        0 as pidx, -- packed item index
        so.docstatus as docstatus
    FROM `tabSales Order Item` as soi
    JOIN `tabSales Order` as so ON soi.parent = so.name
    JOIN `tabItem` as it ON soi.item_code = it.name
    WHERE
        so.docstatus {status_filter} AND
        so.per_delivered < 100 AND
        soi.qty > soi.delivered_qty AND
        so.status != 'Closed' AND
        (so._user_tags NOT LIKE "%template%" OR so._user_tags IS NULL)
        {extra_filters}
	) UNION (
    SELECT
        1 AS indent,
        soi.name,
        pi.name as detail_docname,
        WEEK(soi.delivery_date) as weeknum,
        soi.parent as sales_order,
        so.customer as customer,
        so.customer_name as customer_name,
        pi.qty as qty,
        (soi.qty - soi.delivered_qty) * (pi.qty / soi.qty) AS remaining_qty,
        soi.delivery_date as delivery_date,
        pi.item_code as item_code,
        pi.item_name as item_name,
        NULL as item_group,
        NULL as serial_nos,
        TRUE as is_packed_item,
        soi.idx as idx,
        pi.idx as pidx,
        so.docstatus as docstatus
    FROM `tabSales Order Item` as soi
    JOIN `tabSales Order` as so ON soi.parent = so.name
    JOIN `tabItem` as it on soi.item_code = it.name
    JOIN `tabPacked Item` as pi ON soi.name = pi.parent_detail_docname
    WHERE
        so.docstatus {status_filter} AND
        so.per_delivered < 100 AND
        soi.qty > soi.delivered_qty AND
        so.status != 'Closed' AND
        (so._user_tags NOT LIKE "%template%" OR so._user_tags IS NULL)
	))
  
  SELECT
  	o.*,
    it.is_stock_item,
    it.item_group AS item_group2, -- new name so it doesn't appear in rendered table.

    -- Qty remaining AFTER SO would go through
    IF(it.is_stock_item, p.projected_qty, NULL) as projected_qty,
    IF(it.is_stock_item, p.guaranteed_qty, NULL) as guaranteed_qty,

    -- Qty remaining BEFORE SO would go through
    IF(it.is_stock_item, p.projected_qty - p.qty, NULL) as projected_stock,
    IF(it.is_stock_item, p.guaranteed_qty - p.qty, NULL) as guaranteed_stock,

    wo.name AS work_order,
    wo.status AS wo_status,
    wo.qty AS wo_qty,
    wo.produced_qty AS wo_produced_qty
  FROM o
  JOIN p ON p.detail_docname = o.detail_docname
  JOIN `tabItem` it ON o.item_code = it.item_code  
  LEFT JOIN `tabWork Order` wo ON wo.sales_order_item = o.detail_docname AND wo.docstatus <= 1
  {so_filter}
  ORDER BY 
    delivery_date ASC,
    sales_order,
    idx,
    pidx;
    """.format(projected_stock_query=projected_stock_query, status_filter=status_filter, 
               extra_filters=extra_filters, so_filter=so_filter)

    # print(sql_query)
    data = frappe.db.sql(sql_query, as_dict=True)

    # Check stock levels. 0 = no go, 1 = projected/not started, 2 = projected/wo started, 3 = guaranteed/wo finished
    for row in data:

        # Just ignore enclosures. Looking at fills is enough:
        if row.is_packed_item and row.item_group2 == "Cartridge Enclosures":
            row.projected_stock = None
            row.guaranteed_stock = None
            continue

        # For cartridge refills, status depends on work order:
        if row.is_packed_item and row.item_group2 == "Cartridge Refills" :
            row.projected_stock = None
            row.guaranteed_stock = None

            if not row.work_order:
                row.sufficient_stock = 0
            elif row.wo_status == "Completed":
                row.sufficient_stock = 3
            elif row.wo_status == "In Process":
                row.sufficient_stock = 2
            else:
                row.sufficient_stock = 1
            continue

        # All other stock items, check projected qty (i.e. qty after SO would be filled)
        if row.is_stock_item:
            if row.guaranteed_qty >= 0:
                row.sufficient_stock = 3
            elif row.projected_qty >= 0:
                row.sufficient_stock = 1
            else:
                row.sufficient_stock = 0

            # row.stock_indicator = ["red", "orange", "green"][row.sufficient_stock]

    # Work out deliverability of bundles:
    bundle_name = ''
    bundle_stock = 3
    for row in data[::-1]:
        if not row.is_packed_item and row.name == bundle_name:
            row.sufficient_stock = bundle_stock
            bundle_stock = 3
            continue

        bundle_name = row.name  # docname of the line item
        pi_stock = row.sufficient_stock is None and 2 or row.sufficient_stock
        bundle_stock = min(pi_stock, bundle_stock)

    # Formatting for alternating colours:
    last_week_num = ''
    last_day = ''
    last_so = ''
    week_index = 0
    day_index = 0
    so_index = 0

    # import pprint
    # pp = pprint.PrettyPrinter(indent=4)
    # print("\n\n\n------", pp.pprint([ r for r in data if r.weeknum == 8]))
    
    for row in data:       
        if row['weeknum'] != last_week_num:
            week_index += 1
            last_week_num = row['weeknum']
        
        if row['delivery_date'] != last_day:
            day_index += 1
            last_day = row['delivery_date']

        if row['sales_order'] != last_so:
            so_index += 1
            last_so = row['sales_order']
        row['week_index'] = week_index
        row['day_index'] = day_index
        row['so_index'] = so_index

        row['ship_date'] = row['delivery_date']

        # TODO move to frontend formatting?
        if not row['is_packed_item']:
            row['item_name'] = "<b>{name}</b>".format(name=row['item_name'])

        if row['docstatus'] == 0:
            row['indicator'] = '<span class="indicator whitespace-nowrap red"><span>Draft</span></span>'
        else:
            row['indicator'] = '<span class="indicator whitespace-nowrap orange"><span>To Deliver</span></span>'
    
    return data


def get_chart(filters):

    status_filter = "so.docstatus = 1 AND"
    if filters.include_drafts:
        status_filter = "so.docstatus <= 1 AND" # include drafts and submitted.

    extra_filters = ""
    if filters.only_manufacturing:
        extra_filters += "AND it.include_item_in_manufacturing = TRUE"
        
    sql_query = """
SELECT
    WEEK(soi.delivery_date) as weeknum,
    SUBDATE(soi.delivery_date, WEEKDAY(soi.delivery_date)) as week,
    SUM(soi.qty - soi.delivered_qty) AS remaining_qty,
    it.item_group as item_group
FROM `tabSales Order Item` as soi
JOIN `tabSales Order` as so ON soi.parent = so.name
JOIN `tabItem` as it on soi.item_code = it.name
WHERE
    {status_filter} 
    so.status != 'Closed' AND
    soi.qty > soi.delivered_qty AND
    (so._user_tags NOT LIKE "%template%" OR so._user_tags IS NULL)
    {extra_filters}
GROUP BY week, item_group
ORDER BY week ASC
    """.format(status_filter=status_filter, extra_filters=extra_filters)
    
    data = frappe.db.sql(sql_query, as_dict=True)
    
    # Build dict of arrays, that store the sum of items in each group, each week.
    weeks = sorted(set([it['week'] for it in data]))
    groups = sorted(set([it['item_group'] for it in data]))
    plotdata = {}

    for g in groups:
        plotdata[g] = [0] * len(weeks)

    for item in data:
        week, group, qty = item['week'], item['item_group'], item['remaining_qty']
        plotdata[group][weeks.index(week)] += qty

    # Convert to format expected by Frappe charts
    datasets = []
    for group in plotdata.keys():
        datasets.append({
            "name": ellipsis(group, 12),
            "values": plotdata[group],
        })
    
    chart = {
        "data": {
            "labels": [w.strftime("(W%V) %d-%m-%Y") for w in weeks],
            "datasets": datasets,
        },
        "type": 'bar',
        "barOptions": {
            "stacked": True,
            "spaceRatio": 0.1,
        },
        "title": "Total items per week",
    }
    return chart
    
    
### Helpers

def ellipsis(text, length=10):
    if len(text) <= length:
        return text
    return text[:int(length/2)-1] + "…" + text[-int(length/2):]
