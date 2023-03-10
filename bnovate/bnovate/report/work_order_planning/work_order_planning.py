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

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
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

    return [
        {'fieldname': 'sufficient_stock', 'fieldtype': 'Data', 'label': _('Go?'), 'width': 50},
        {'fieldname': 'work_order', 'fieldtype': 'Link', 'label': _('Work Order'), 'options': 'Work Order', 'width': 100},
        {'fieldname': 'workstation', 'fieldtype': 'Data', 'label': _('Workstation'), 'width': 100, 'align': 'left'},
        {'fieldname': 'status', 'fieldtype': 'Data', 'label': _('Status'), 'width': 100},
        {'fieldname': 'planned_start_date', 'fieldtype': 'Date', 'label': _('Start date'), 'width': 80},
        {'fieldname': 'expected_delivery_date', 'fieldtype': 'Date', 'label': _('Delivery date'), 'width': 80},
        {'fieldname': 'qty', 'fieldtype': 'Float', 'label': _('Qty'), 'width': 100},
        {'fieldname': 'item_code', 'fieldtype': 'Data', 'label':_('Item'), 'options': 'Item', 'width': 300, 'align': 'left'},
        {'fieldname': 'comment', 'fieldtype': 'Data', 'label': _('Comment'), 'width': 200, 'align': 'left'},
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
    ]

def get_data(filters):

    # Build a full projection of the stock (similar to Projected Stock report),
    # then check for each work order the projected stock of the required items.
    # If projected stock is negative, it means there wasn't enough stock

    workstation_filter = ""
    if filters.workstation:
        workstation_filter = "AND wo2.workstation = '{}'".format(filters.workstation)

    sql_query = """
-- End goal: a table where each row is either a work order production item or required item, with projected stock once WO is completed.
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
    wo.status,
    wo.comment,
    wo.workstation,

    -- Fields for Work Order Items (consumed items)
    woi.required_qty AS reqd_item_qty,
    woi.consumed_qty AS reqd_item_consumed_qty,
    (woi.required_qty - woi.consumed_qty) AS reqd_item_required_qty


FROM (
  -- This monster is the "projected stock" query: projected stock after each upcoming stock transaction (WO, SO, PO)
  SELECT 
      *,
      ROUND(SUM(e.qty) 
        OVER ( PARTITION BY e.item_code, e.warehouse ORDER BY e.order_prio, e.date ASC, e.docname )
      , 3) AS projected_qty,
      ROUND(SUM(IF(e.detail_doctype in ("Purchase Order Item", "Work Order"), 0, e.qty)) 
        OVER ( PARTITION BY e.item_code, e.warehouse ORDER BY e.order_prio, e.date ASC, e.docname )
      , 3) AS guaranteed_qty
  FROM (
    (SELECT
      0 as order_prio, -- to keep stock balance as first item in list
      CURDATE() as date,
      'Stock Balance' as `doctype`,
      null as `docname`,
      null as `detail_docname`,
      null as `detail_doctype`,
      b.item_code,
      b.warehouse,
      b.actual_qty as qty,
      b.stock_uom
    FROM `tabBin` as b
  ) UNION ALL (
  -- Sales Order: items to sell
    SELECT
      1 as order_prio,
      soi.delivery_date as `date`,
      'Sales Order' as `doctype`,
      soi.parent as `docname`,
      soi.name as `detail_docname`,
      'Sales Order Item' as `detail_doctype`,
      soi.item_code,
      soi.warehouse,
      -(soi.qty - soi.delivered_qty) * soi.conversion_factor as qty,
        soi.stock_uom
    FROM `tabSales Order Item` as soi
    JOIN `tabSales Order` as so ON so.name = soi.parent
    WHERE soi.delivered_qty < soi.qty
      AND soi.docstatus = 1
      AND so.status != 'Closed'
  ) UNION ALL (
  -- Packed items: items to sell inside bundles
    SELECT
      1 as order_prio,
      soi.delivery_date as `date`,
      'Sales Order' as `doctype`,
      soi.parent as `docname`,
      pi.name as `detail_docname`,
      'Packed Item' as `detail_doctype`,
      pi.item_code,
      pi.warehouse,
      ROUND(-(soi.qty - soi.delivered_qty) / soi.qty * pi.qty, 3) as qty, -- soi conversion factor already calculated in packed item qty!
        pi.uom as stock_uom
    FROM `tabPacked Item` as pi
    JOIN `tabSales Order` as so ON so.name = pi.parent
    JOIN `tabSales Order Item` as soi on soi.name = pi.parent_detail_docname
    WHERE soi.delivered_qty < soi.qty
      AND soi.docstatus = 1
      AND so.status != 'Closed'
  ) UNION ALL (
  -- Purchase Order: items to receive
    SELECT    
      1 as order_prio,
      IFNULL(poi.expected_delivery_date, poi.schedule_date) as `date`,
      'Purchase Order' as `doctype`,
      poi.parent as `docname`,
      poi.name as `detail_docname`,
      'Purchase Order Item' as `detail_doctype`,
      poi.item_code,
      poi.warehouse,
      (poi.qty - poi.received_qty) * poi.conversion_factor as qty,
        poi.stock_uom
    FROM `tabPurchase Order Item` as poi
    JOIN `tabPurchase Order` as po ON po.name = poi.parent
    WHERE poi.received_qty < poi.qty
      AND poi.docstatus = 1
      AND po.status != 'Closed'
  ) UNION ALL (
  -- Work Orders: produced items
  SELECT
      1 as order_prio,
      IFNULL(wo.expected_delivery_date, CAST(wo.planned_start_date AS date)) as `date`,
      "Work Order" as `doctype`,
      wo.name as `docname`,
      wo.name as `detail_docname`,
      'Work Order' as `detail_doctype`,
      wo.production_item as `item_code`,
      wo.fg_warehouse,
      wo.qty - wo.produced_qty as `qty`,
        wo.stock_uom
  FROM `tabWork Order` as wo
  WHERE wo.docstatus < 2 -- Allow drafts on work orders
      AND wo.qty > wo.produced_qty
      AND wo.status != 'Stopped'
  ) UNION ALL (
  -- Work Order Items: consumed items
  SELECT
      1 as order_prio,
      CAST(wo.planned_start_date AS date) as `date`,
      "Work Order" as `doctype`,
      wo.name as `docname`,
      woi.name as `detail_docname`,
      'Work Order Item' as `detail_doctype`,
      woi.item_code as `item_code`,
      woi.source_warehouse as `warehouse`,
      -(woi.required_qty - woi.consumed_qty) as `qty`,
        "" as stock_uom
  FROM `tabWork Order Item` as woi
  JOIN `tabWork Order` as wo ON woi.parent = wo.name
  WHERE wo.docstatus < 2  -- Allow drafts on work orders
      AND wo.qty > wo.produced_qty
      AND wo.status != 'Stopped'
  )) as e -- "entries"
) as p -- "projected"

LEFT JOIN `tabWork Order Item` woi on woi.name = p.detail_docname
LEFT JOIN `tabWork Order` wo on wo.name = p.detail_docname
JOIN `tabItem` it on p.item_code = it.name
JOIN `tabWork Order` wo2 on p.docname = wo2.name -- To filter all rows on WO properties.

WHERE p.doctype = "Work Order"
  {workstation_filter}
ORDER BY wo2.planned_start_date, p.docname, p.detail_doctype -- Put 'Work Order Item's below 'Work Order's
    """.format(workstation_filter=workstation_filter)

    data = frappe.db.sql(sql_query, as_dict=True)

    # Check stock levels. 0 = no go, 1 = projected, 2 = guaranted
    idx = 0
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
            

    # import pprint
    # pp = pprint.PrettyPrinter(indent=4)
    # print("\n\n\n------", pp.pprint([r for r in data if r.item_code == "100072"]))

    return data

