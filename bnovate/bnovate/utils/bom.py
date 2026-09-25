# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe


@frappe.whitelist()
def should_show_inherit_expiry_date(production_item=None, input_items=None):
    """ Whether the BOM's "Inherit Expiry Date From" field should be shown:
    the produced item must itself be batch- and expiry-tracked, and at least
    one of the given input items must be expiry-tracked too.
    """
    if isinstance(input_items, str):
        input_items = frappe.parse_json(input_items)
    input_items = list(set(filter(None, input_items or [])))

    if not production_item or not input_items:
        return False

    production_item_flags = frappe.db.get_value(
        "Item", production_item, ["has_batch_no", "has_expiry_date"]
    )
    if not production_item_flags or not all(production_item_flags):
        return False

    return bool(frappe.db.get_value(
        "Item", {"item_code": ["in", input_items], "has_expiry_date": 1}, "name"
    ))
