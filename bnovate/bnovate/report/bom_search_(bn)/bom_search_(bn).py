# Copyright (c) 2025, bNovate, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json

from six import iteritems

def execute(filters=None):

    return get_columns(), get_data(filters)


def get_columns():
    return [
        {
            "fieldname": "name",
            "label": "BOM",
            "width": 200,
            "fieldtype": "Link",
            "options": "BOM",
            "align": "left"
        },
        {
            "fieldname": "bundle_name",
            "label": "Bundle",
            "width": 200,
            "fieldtype": "Link",
            "options": "Product Bundle",
            "align": "left"
        },
        {
            "fieldname": "item",
            "label": "Output Item Code",
            "width": 250,
            "fieldtype": "Link",
            "options": "Item"
        },
        # {
        #     "fieldname": "item_name",
        #     "label": "Item Name",
        #     "width": 180,
        #     "fieldtype": "Data"
        # },
        {
            "fieldname": "bom_description",
            "label": "BOM Description",
            "width": 200,
            "fieldtype": "Data",
            "align": "left"
        },
        {
            "fieldname": "item_qty",
            "label": "Input Qty",
            "width": 100,
            "fieldtype": "Float"
        },
        {
            "fieldname": "bom_qty",
            "label": "Output Qty",
            "width": 100,
            "fieldtype": "Float"
        },
        {
            "fieldname": "is_active",
            "label": "Is Active?",
            "width": 50,
            "fieldtype": "Check"
        },
        {
            "fieldname": "is_default",
            "label": "Is Default?",
            "width": 50,
            "fieldtype": "Check"
        },
        {
            "fieldname": "item_disabled",
            "label": "Output Item Disabled?",
            "width": 50,
            "fieldtype": "Check"
        }
    ]	

def get_data(filters):
    doctype = "BOM Explosion Item" if filters.search_sub_assemblies else "BOM Item"

    additional_filters = ""
    if filters.only_active:
        additional_filters += " AND bom.is_active = 1"
    if filters.only_default:
        additional_filters += " AND bom.is_default = 1"
    if filters.only_active_items:
        additional_filters += " AND item.disabled = 0"

    additional_bundle_filters = ""
    if filters.only_active_items:
        additional_bundle_filters += " AND item.disabled = 0"

    query = """
    SELECT
        bom.name,
        NULL as bundle_name,
        bom.item,
        bom.item_name,
        bom.bom_description,
        bom.is_active,
        bom.is_default,
        bom.quantity AS bom_qty,
        bi.qty AS item_qty,
        item.disabled AS item_disabled
    FROM `tab{doctype}` bi
    JOIN `tabBOM` bom ON bom.name = bi.parent
    JOIN `tabItem` item ON item.item_code = bom.item
    WHERE bi.item_code = "{item1}"
        {additional_filters}

    UNION ALL
    
    SELECT
        NULL as name,
        bundle.name as bundle_name,
        bundle.new_item_code as item,
        item.item_name as item_name,
        bundle.description as bom_description,
        1 as is_active,
        1 as is_default,
        1 as bom_qty,
        bi.qty as item_qty,
        item.disabled as item_disabled
    FROM `tabProduct Bundle Item` bi
    JOIN `tabProduct Bundle` bundle ON bundle.name = bi.parent
    JOIN `tabItem` item ON item.item_code = bundle.new_item_code
    WHERE bi.item_code = "{item1}"
        {additional_bundle_filters}
    """.format(doctype=doctype, item1=filters.item1, additional_filters=additional_filters, additional_bundle_filters=additional_bundle_filters)

    return frappe.db.sql(query, as_dict=1)
 
     