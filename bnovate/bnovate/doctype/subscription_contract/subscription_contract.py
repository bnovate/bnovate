# -*- coding: utf-8 -*-
# Copyright (c) 2023, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, nowdate, getdate
from erpnext.selling.doctype.quotation.quotation import _make_customer

class SubscriptionContract(Document):
	pass

@frappe.whitelist()
def make_from_quotation(source_name, target_doc=None):
	quotation = frappe.db.get_value("Quotation", source_name, ["transaction_date", "valid_till"], as_dict = 1)
	if quotation.valid_till and (quotation.valid_till < quotation.transaction_date or quotation.valid_till < getdate(nowdate())):
		frappe.throw(_("Validity period of this quotation has ended."))
	return _make_from_quotation(source_name, target_doc)

def _make_from_quotation(source_name, target_doc=None, ignore_permissions=False):
	customer = _make_customer(source_name, ignore_permissions)

	def set_missing_values(source, target):
		if customer:
			target.customer = customer.name
			target.customer_name = customer.customer_name
		target.ignore_pricing_rule = 1
		target.flags.ignore_permissions = ignore_permissions

	def update_item(obj, target, source_parent):
		target.stock_qty = flt(obj.qty) * flt(obj.conversion_factor)

	doclist = get_mapped_doc("Quotation", source_name, {
			"Quotation": {
				"doctype": "Subscription Contract",
				"validation": {
					"docstatus": ["=", 1]
				}
			},
			"Quotation Item": {
				"doctype": "Subscription Contract Item",
				"field_map": {
					"parent": "prevdoc_docname"
				},
				"condition": is_subscription_item,
				"postprocess": update_item
			},
			"Sales Taxes and Charges": {
				"doctype": "Sales Taxes and Charges",
				"add_if_empty": True
			},
		}, target_doc, set_missing_values, ignore_permissions=ignore_permissions)


	return doclist

def is_subscription_item(quotation_item):
	""" Return true if item line from QTN is a subscription-able item """
	return bool(frappe.db.get_value("Item", quotation_item.item_code, "enable_deferred_revenue"))