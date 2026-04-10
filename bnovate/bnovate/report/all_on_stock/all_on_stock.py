# Copyright (c) 2013-2026, libracore and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = get_columns()
    data = get_data_with_snr(filters)

    return columns, data

def get_columns():
    return [
        {"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
        {"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link",  "options": "Warehouse", "width": 150},
        #{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data",  "width": 100},
        #{"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group",  "width": 120},
        {"label": _("SNR"), "fieldname": "snr", "fieldtype": "Data", "width": 100},
        {"label": _("Quantity"), "fieldname": "qty", "fieldtype": "Float", "width": 100},
        {"label": _("Stock UOM"), "fieldname": "stock_uom", "fieldtype": "Link", "width": 100, "options": "UOM"},
        {"label": _("Value"), "fieldname": "value", "fieldtype": "Currency", "width": 100},
        {"label": _("Disabled"), "fieldname": "disabled", "fieldtype": "Check", "width": 50},
        {"label": _(""), "fieldname": "blank", "fieldtype": "Data", "width": 20}
    ]

def get_data(filters):
    # get all item/warehouse combinations
    item_warehouse_query = """SELECT DISTINCT(CONCAT(`tabStock Ledger Entry`.`item_code`, "::", `tabStock Ledger Entry`.`warehouse`)) AS `key`, 
          `tabStock Ledger Entry`.`item_code`, 
          `tabStock Ledger Entry`.`warehouse`,
          `tabItem`.`has_serial_no`
        FROM `tabStock Ledger Entry`
        LEFT JOIN `tabItem` ON `tabStock Ledger Entry`.`item_code` = `tabItem`.`name`;"""
    item_warehouses = frappe.db.sql(item_warehouse_query, as_dict=True)
    
    # prepare target list
    stock_levels = []
    
    for item_warehouse in item_warehouses:
        # get stock level per warehouse based on last level from stock ledger
        stock_level = frappe.db.sql("""
			SELECT `qty_after_transaction` AS `qty`, 
				`stock_value` AS `value`
		    FROM `tabStock Ledger Entry` AS `sle1`
		    WHERE `sle1`.`item_code` = %(item_code)s

			   AND `sle1`.`posting_date` <= %(date)s
			   AND `sle1`.`warehouse` LIKE %(warehouse)s
		    ORDER BY `posting_date` DESC, `posting_time` DESC, `modified` DESC
		    LIMIT 1;
		    """,
		    {
				'item_code': item_warehouse['item_code'], 
                'warehouse': item_warehouse['warehouse'],
                'date': filters.get("date")
            }, 
            as_dict=True
        )

        if stock_level[0]['qty'] > 0 or stock_level[0]['value'] > 0:
            stock_levels.append({
                'item_code': item_warehouse['item_code'],
                'warehouse': item_warehouse['warehouse'],
                'snr': item_warehouse['has_serial_no'],
                'qty': stock_level[0]['qty'],
                'value': stock_level[0]['value']
            })
        
    return stock_levels

def get_data_with_snr(filters):
    # get all item/warehouse combinations
    item_warehouse_query = """SELECT DISTINCT(CONCAT(`tabStock Ledger Entry`.`item_code`, "::", `tabStock Ledger Entry`.`warehouse`)) AS `key`, 
          `tabStock Ledger Entry`.`item_code`, 
          `tabStock Ledger Entry`.`warehouse`,
          `tabItem`.`has_serial_no` AS `has_serial_no`,
          `tabItem`.`stock_uom` AS `stock_uom`,
          `tabItem`.`disabled` AS `disabled`,
          `tabSerial No`.`name` AS `serial_no`
        FROM `tabStock Ledger Entry`
        LEFT JOIN `tabItem` ON `tabStock Ledger Entry`.`item_code` = `tabItem`.`name`
        LEFT JOIN `tabSerial No` ON (`tabSerial No`.`warehouse` = `tabStock Ledger Entry`.`warehouse` 
                            AND `tabSerial No`.`item_code` = `tabStock Ledger Entry`.`item_code`);"""
    item_warehouses = frappe.db.sql(item_warehouse_query, as_dict=True)
    
    # prepare target list
    stock_levels = []
    
    for item_warehouse in item_warehouses:
        # get stock level per warehouse based on last level from stock ledger
        stock_level = frappe.db.sql("""
			SELECT `qty_after_transaction` AS `qty`, 
				`stock_value` AS `value`
		    FROM `tabStock Ledger Entry` AS `sle1`
		    WHERE `sle1`.`item_code` = %(item_code)s

			   AND `sle1`.`posting_date` <= %(date)s
			   AND `sle1`.`warehouse` LIKE %(warehouse)s
		    ORDER BY `posting_date` DESC, `posting_time` DESC, `modified` DESC
		    LIMIT 1;""", 
		    {
				'item_code': item_warehouse['item_code'], 
                'warehouse': item_warehouse['warehouse'],
                'date': filters.get("date")
            },
			as_dict=True
		)

        if len(stock_level) > 0 and (flt(stock_level[0].get('qty')) > 0 or flt(stock_level[0].get('value')) > 0):
            item = {
                'item_code': item_warehouse['item_code'],
                'warehouse': item_warehouse['warehouse'],
                'qty': stock_level[0]['qty'],
                'stock_uom': item_warehouse['stock_uom'],
                'value': stock_level[0]['value'],
                'disabled': item_warehouse['disabled']
            }
            if item_warehouse['has_serial_no']:
                item['snr'] = item_warehouse['serial_no']
                item['qty'] = 1
                item['value'] = stock_level[0]['value'] / stock_level[0]['qty']
            stock_levels.append(item)
        
    return stock_levels
