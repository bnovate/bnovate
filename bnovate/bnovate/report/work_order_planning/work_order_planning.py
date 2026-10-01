# Copyright (c) 2023, bNovate, libracore, and contributors
# For license information, please see license.txt
#
# WORK ORDER PLANNING
#####################
#
# Show which open work orders are executable based on inventory levels.
#
###################################################################

from __future__ import unicode_literals
import frappe
from frappe import _
from collections import OrderedDict
from urllib.parse import quote

from bnovate.bnovate.report.projected_stock import projected_stock

def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data

def get_columns(filters):
    guaranteed_info = """
<p>Guaranteed stock before WO is executed.</p>

<p align='left'>Calculation: 
<ul>
    <li>Current stock balance</li>
    <li>- items <b>consumed</b> by WO (at <i>start date</i>)</li>
    <li>- SO (at <i>ship date</i>)</li>
</ul>
</p>
"""

    projected_info = """
<p>Projected stock before WO is executed.</p>

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

    cols = [
        {'fieldname': 'sufficient_stock', 'fieldtype': 'Data', 'label': _('Go?'), 'width': 50},
        {'fieldname': 'work_order', 'fieldtype': 'Data', 'label': _('Work Order'), 'options': 'Work Order', 'width': 100},
        {'fieldname': 'workstation', 'fieldtype': 'Data', 'label': _('Workstation'), 'width': 100, 'align': 'left'},
        {'fieldname': 'status', 'fieldtype': 'Data', 'label': _('Status'), 'width': 100},
        {'fieldname': 'planned_start_date', 'fieldtype': 'Date', 'label': _('Start date'), 'width': filters.simple_view and 80 or 120},
        {'fieldname': 'expected_delivery_date', 'fieldtype': 'Date', 'label': _('Delivery date'), 'width': 80},
        {'fieldname': 'qty', 'fieldtype': 'Float', 'label': _('Qty'), 'width': 100},
        {'fieldname': 'item_code', 'fieldtype': 'Data', 'label':_('Item'), 'options': 'Item', 'width': 300, 'align': 'left'},
        {'fieldname': 'sales_order', 'fieldtype': 'Link', 'label': _('Sales Order'), 'options': 'Sales Order', 'width': 100},
        {'fieldname': 'serial_no', 'fieldtype': 'Data', 'label': _('Serial No'), 'width': 200, 'align': 'left'},
        {'fieldname': 'bom_description', 'fieldtype': 'Data', 'label': _('BOM Description'), 'width': 200, 'align': 'left'},
        {'fieldname': 'comment', 'fieldtype': 'Data', 'label': _('Comment'), 'width': 200, 'align': 'left'},
    ]

    if not filters.simple_view:
        cols.extend([
            {'fieldname': 'item_group', 'fieldtype': 'Data', 'label': _('Item Group'), 'width': 100},
            {'fieldname': 'projected_stock', 'fieldtype': 'Int', 
                'label': '<span data-html="true" data-toggle="tooltip" data-placement="bottom" data-container="body" title="{}">Proj. Stock <i class="fa fa-info-circle"></i></span>'.format(projected_info), 
                'width': 110},
            {'fieldname': 'guaranteed_stock', 'fieldtype': 'Int', 
                'label': '<span data-html="true" data-toggle="tooltip" data-placement="bottom" data-container="body" title="{}">Guar. Stock <i class="fa fa-info-circle"></i></span>'.format(guaranteed_info), 
                'width': 110},
            # {'fieldname': 'projected_qty', 'fieldtype': 'Int', 'label': 'Proj. AFTER WO', 'width': 110},
            # {'fieldname': 'guaranteed_qty', 'fieldtype': 'Int', 'label': 'Guar. AFTER WO', 'width': 110},
            {'fieldname': 'stock_uom', 'fieldtype': 'Data', 'label': _('Unit'), 'width': 100},
            {'fieldname': 'warehouse', 'fieldtype': 'Data', 'label': _('Warehouse'), 'width': 100},
            {'fieldname': 'mean_time_per_unit', 'fieldtype': 'Data', 'precision': 1, 'label': _('Mean Minutes per Unit'), 'width': 100, 'align': 'right'}, # Also fomratted as data for hh:mm display
            {'fieldname': 'time_estimate_remaining', 'fieldtype': 'Data', 'label': _('Time Estimate'), 'width': 100, 'align': 'right'}, # formatted as Data for hh:mm display...
        ])

    return cols

def get_data(filters):

    # Build a full projection of the stock (similar to Projected Stock report),
    # then check for each work order the projected stock of the required items.
    # If projected stock is negative, it means there wasn't enough stock

    workstation_filter = ""
    if filters.workstation:
        workstation_filter = "AND wo2.workstation = '{}'".format(filters.workstation)

    projected_stock_query = projected_stock.build_query(so_drafts=False, wo_drafts=True, item_code=None, warehouse=None)
    sql_query = """
-- End goal: a table where each row is either a work order production item or required item, with projected stock once WO is completed.
WITH
    -- Time Estimates
    te as (SELECT
            wo.production_item AS item_code,
            AVG(wo.time_per_unit) AS mean_time_per_unit
        FROM `tabWork Order` wo
        WHERE wo.time_per_unit > 0
        GROUP BY wo.production_item)

SELECT 

    -- Common fields
    IF(p.detail_doctype = "Work Order", 0, 1) AS indent,
    p.docname AS work_order,
    p.item_code,
    ROUND(p.qty, 3) AS qty,
    -- Qty remaining AFTER WO...
    p.projected_qty,  -- ...if all planned SO, WO and PO go through
    p.guaranteed_qty, -- ...taking only items CONSUMED by WO and SO.
    -- Qty remaining BEFORE WO
    (p.projected_qty - p.qty) AS projected_stock,
    (p.guaranteed_qty - IF(p.detail_doctype = "Work Order", 0, p.qty)) AS guaranteed_stock, -- Work orders were already subtracted by a filter lower down
    p.warehouse,
    it.stock_uom,
    it.item_name,
    it.item_group,
    p.detail_doctype,
    
    -- Fields for Work Orders (produced items)
    wo.workstation,
    wo.planned_start_date,
    wo.planned_end_date,
    wo.expected_delivery_date,
    wo.qty as planned_qty,
    wo.produced_qty,
    (wo.qty - wo.produced_qty) AS required_qty,
    wo.docstatus,
    wo.status,
    wo.serial_no,
    wo.comment,
    wo.sales_order,
    wo.bom_description,
    te.mean_time_per_unit,
    te.mean_time_per_unit * (wo.qty - wo.produced_qty) AS time_estimate_remaining,

    -- Fields for Work Order Items (consumed items)
    woi.required_qty AS reqd_item_qty,
    woi.consumed_qty AS reqd_item_consumed_qty,
    (woi.required_qty - woi.consumed_qty) AS reqd_item_required_qty


FROM (
  -- This monster is the "projected stock" query: projected stock after each upcoming stock transaction (WO, SO, PO)
  {projected_stock_query}
) as p -- "projected"

LEFT JOIN `tabWork Order Item` woi on woi.name = p.detail_docname
LEFT JOIN `tabWork Order` wo on wo.name = p.detail_docname
LEFT JOIN te on wo.production_item = te.item_code
JOIN `tabItem` it on p.item_code = it.name
JOIN `tabWork Order` wo2 on p.docname = wo2.name -- To filter all rows on WO properties.

WHERE p.doctype = "Work Order"
  {workstation_filter}
ORDER BY wo2.planned_start_date, p.docname, p.detail_doctype -- Put 'Work Order Item's below 'Work Order's
    """.format(projected_stock_query=projected_stock_query, workstation_filter=workstation_filter)

    data = frappe.db.sql(sql_query, as_dict=True)

    # Check stock levels. 0 = no go, 1 = projected, 2 = guaranted
    idx = 0  # For alternating colours
    wo_go = 2
    for row in data[::-1]: 
        if row.detail_doctype == "Work Order":
            row.idx = idx
            row.sufficient_stock = wo_go
            idx += 1
            wo_go = 2
            continue
        
        go = 0
        if row.guaranteed_qty >= 0:
            go = 2
        elif row.projected_qty >= 0:
            go = 1
        row.sufficient_stock = go

        wo_go = min(go, wo_go)

    for row in data:
        row.stock_indicator = ["red", "orange", "green"][row.sufficient_stock]

    if filters.simple_view:
        data = [row for row in data if  row.docstatus == 1]

    # import pprint
    # pp = pprint.PrettyPrinter(indent=4)
    # print("\n\n\n------", pp.pprint([r for r in data if r.item_code == "100072"]))

    return data

