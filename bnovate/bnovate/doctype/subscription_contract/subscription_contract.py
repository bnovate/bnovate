# -*- coding: utf-8 -*-
# Copyright (c) 2023, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import json
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, nowdate, getdate, add_days, date_diff
from erpnext.selling.doctype.quotation.quotation import _make_customer
from erpnext.controllers.selling_controller import SellingController
from erpnext.controllers.sales_and_purchase_return import make_return_doc

from bnovate.bnovate.report.aggregate_invoicing.aggregate_invoicing import check_invoice_status

class SubscriptionContract(SellingController):
	def validate(self):

		self.set_status()

	def on_cancel(self):
		frappe.db.set(self, 'status', 'Cancelled')

	def set_status(self):
		if self.docstatus == 2:
			self.status = "Cancelled"
		elif self.docstatus == 1:
			if self.stopped:
				self.status = "Stopped"
			elif getdate(self.end_date) < getdate(nowdate()):
				self.status = "Finished"
			else:
				self.status = "Active"
		else:
			self.status = "Draft"

		self.db_set('status', self.status)

def update_subscription_status():
	""" Update status on finished contracts. Called daily (hooks.py). """
	frappe.db.sql("""
		UPDATE `tabSubscription Contract` SET status = 'Finished'
		WHERE end_date < CURDATE() AND docstatus = 1
	""")

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
	return bool(frappe.db.get_value("Item", quotation_item.item_code, "bn_requires_deferral"))

@frappe.whitelist()
def make_from_self(source_name, target_doc=None):
	""" Make a copy of the subscription, but starting at the end date of previous one.

	Can be used to renew or modify (upgrade) a subscription.
	"""
	closing_doc = frappe.db.get_value("Subscription Contract", source_name, ["end_date"], as_dict=1)

	end_date = closing_doc.end_date
	if not end_date:
		end_date = nowdate()
	
	def postprocess(source, target):
		target.stopped = False
		target.credit_confirmed = False
		target.start_date = add_days(end_date, 1) 
		target.end_date = None
		target.planned_end_date = None
		target.amended_from = source_name

	return get_mapped_doc("Subscription Contract", source_name, {
		"Subscription Contract": {
			"doctype": "Subscription Contract",
		}
	}, postprocess=postprocess)

@frappe.whitelist()
def end_contract(docname, end_date=None):
	""" End a subscription before the planned end date """
	if end_date is None:
		end_date = nowdate()

	# Ensure billing is up to date
	missing_invoices = check_invoice_status(docname, end_date)
	if len(missing_invoices) > 0:
		frappe.msgprint(_("Please create all invoices up until the chosen end date."), raise_exception=True)

	doc = frappe.get_doc("Subscription Contract", docname)
	if getdate(end_date) < getdate(doc.start_date):
		frappe.msgprint(_("End date must be later than start date."), raise_exception=True)
	doc.db_set("end_date", end_date)
	doc.db_set("stopped", True)
	doc.db_set("status", "Stopped")

@frappe.whitelist()
def stop_invoices(docname):
	""" Set stop date of existing SINVs for this subscription """

	frappe.has_permission('Sales Invoice', 'write', throw=True)

	# Find associated sales invoice items and matching credit notes, if any
	doc = frappe.get_doc("Subscription Contract", docname)
	if not doc.end_date:
		frappe.msgprint(_("End date must be defined."), raise_exception=True)
	end_date = doc.end_date
	items = [it.name for it in doc.items]
	query = """
	WITH sinv_items as (
		SELECT
			sii.parent as sinv_name,
			sii.name,
			sii.service_start_date,
			sii.service_end_date,
			sii.service_stop_date,
			sii.idx,
			sii.qty,
			sii.net_amount,
			sii.net_rate,
			sii.sc_detail,
			si.currency
		FROM `tabSales Invoice Item` sii
		JOIN `tabSales Invoice` si ON sii.parent = si.name
		WHERE sii.sc_detail IN {items} 
			AND sii.docstatus = 1
			AND si.is_return = 0
	), ret_items as (
		SELECT
			sii.parent as credit_note,
			sii.net_amount as refunded_amount,
			sii.sc_detail,
			sii.service_start_date
		FROM `tabSales Invoice Item` sii
		JOIN `tabSales Invoice` si ON sii.parent = si.name
		WHERE sii.sc_detail IN {items}
			AND sii.docstatus = 1
			AND si.is_return = 1
	)
	SELECT 
		sinv_items.*,
		credit_note,
		refunded_amount
	FROM sinv_items
	LEFT JOIN ret_items ON sinv_items.sc_detail = ret_items.sc_detail AND sinv_items.service_start_date = ret_items.service_start_date
	""".format(items='("' + '", "'.join(items) + '")')
	sinv_items = frappe.db.sql(query, {'items': items}, as_dict=True)

	# For any item within current or future billing period (relative to end_date), stop service early
	# and calculate refund amount
	matching_items = []
	for si in sinv_items:
		if getdate(end_date) < si.service_end_date and si.refunded_amount is None:

			matching_items.append(si)

			stop_date = max(getdate(end_date), si.service_start_date)
			frappe.db.set_value("Sales Invoice Item", si.name, "service_stop_date", stop_date)

			# Calculate refund amount
			period_days = (si.service_end_date - si.service_start_date).days
			remaining_days = (si.service_end_date - stop_date).days

			si.refund = si.net_amount * remaining_days / period_days
			si.refund_rate = si.net_rate * remaining_days / period_days

	return matching_items


@frappe.whitelist()
def create_credit_notes(docname, sinv_items, selected_items):
	""" Create credit notes for sinv_items as returned by close(), only for item names in selected_items """

	frappe.has_permission('Sales Invoice', 'write', throw=True)

	doc = frappe.get_doc("Subscription Contract", docname)
	doc.db_set("credit_confirmed", True)

	sinv_items = json.loads(sinv_items)
	selected_items = json.loads(selected_items)
	
	filtered = [ frappe._dict(it) for it in sinv_items if it['name'] in selected_items]
	invoices = {}
	refunds = {}
	for it in filtered:
		if it.sinv_name not in invoices:
			invoices[it.sinv_name] = [it]
		else:
			invoices[it.sinv_name].append(it)

		if it.sc_detail not in refunds:
			refunds[it.sc_detail] = {}

		refunds[it.sc_detail][getdate(it.service_start_date)] = it.refund_rate

	# Create Credit Note for each invoice
	credit_notes = []
	for sinv_name, items in invoices.items():
		# Inspired by make_mapped_doc: flags are read by get_mapped_doc, which is called
		# by make_return_doc()
		frappe.flags.selected_children = {'items': [ it.name for it in items]}
		sinv_ret = make_return_doc("Sales Invoice", sinv_name)
		sinv_ret.naming_series = "SINV-RET-"

		# Set refund amount
		for item in sinv_ret.items:
			item.price_list_rate = refunds[item.sc_detail][item.service_start_date]
			item.rate = refunds[item.sc_detail][item.service_start_date]
			item.enable_deferred_revenue = False

		sinv_ret.insert()
		credit_notes.append(sinv_ret)

	return credit_notes


