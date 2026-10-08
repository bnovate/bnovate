# -*- coding: utf-8 -*-
# Copyright (c) 2023-2025, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc, map_child_doc, map_doc

from bnovate.bnovate.utils import add_warning
from erpnext.controllers.queries import get_match_cond
from erpnext.selling.doctype.quotation.quotation import _make_sales_order as _make_sales_order_from_quotation

BILLING_QUOTATION = "According to Quotation"
BILLING_SERVICE_AGREEMENT = "Under Service Agreement"

CHANNEL_DIRECT = "Direct"
CHANNEL_PARTNER = "Service Partner"

BILLING_PARTNER = "Through Service Partner"

# Pricing copied from the Quotation Item to the Sales Order Item
QUOTATION_PRICING_FIELDS = (
    "price_list_rate", "discount_percentage", "discount_amount", "margin_type", "margin_rate_or_amount", "rate",
)

class ServiceReport(Document):

    def set_status(self):
        self.set_so_docstatus()

        if self.docstatus == 2:
            self.status = "Cancelled"
        elif self.docstatus == 1:
            if self.channel == CHANNEL_PARTNER:
                self.status = "Submitted"
            else:
                if self.ignore_billing or self.so_docstatus == 1:
                    self.status = "Submitted"
                else:
                    self.status = "To Bill"
        else:
            self.status = "Draft"

        self.db_set('status', self.status)

    def validate(self):
        # Ensure there are no unnecessary links
        if self.billing_basis !=  BILLING_QUOTATION:
            self.quotation = None
        if self.billing_basis != BILLING_SERVICE_AGREEMENT:
            self.subscription= None

        if self.channel == CHANNEL_PARTNER:
            self.bnovate_technician = None
            self.bnovate_technician_name = None
            self.billing_basis = BILLING_PARTNER
        elif self.channel == CHANNEL_DIRECT:
            self.technician = None
            self.technician_name = None
            self.service_partner = None
            self.service_partner_name = None

        self.set_status()

    def on_cancel(self):
        self.set_status()

    def on_update_after_submit(self):
        self.set_status()

    def before_submit(self):
        pass

        # # Check that all items are available in personal stock
        # levels = get_stock_levels(self.set_warehouse)
        # for row in self.items:
        # 	print(row.item_code, row.qty)
        # 	if row.item_code in levels and levels[row.item_code] >= row.qty:
        # 		continue
        # 	raise Exception("Insufficiant stock for item {item_code}.".format(item_code=row.item_code))

    def set_so_docstatus(self):
        so_docstatus = get_billing_status(self.name)
        self.db_set('so_docstatus', so_docstatus)

def find_so(service_report_docname):
    so_match = frappe.db.sql("""
        SELECT 
            DISTINCT(soi.parent) as sales_order, 
            soi.docstatus as docstatus 
        FROM `tabSales Order Item` soi 
        WHERE soi.service_report = '{0}'
        """.format(service_report_docname))

    return so_match

@frappe.whitelist()
def get_billing_status(service_report_docname):
    """ Return 0 if a SO draft exists, 1 if a submitted one exists, or 2 if no SO exist or all are cancelled """

    so_match = frappe.db.sql("""
        SELECT 
            DISTINCT(soi.parent) as sales_order, 
            soi.docstatus as docstatus 
        FROM `tabSales Order Item` soi 
        WHERE soi.service_report = '{0}'
        """.format(service_report_docname))

    # Format: [ ['SO-XYZ', 0] ] , there can be several rows if SO were cancelled etc.

    print(so_match)

    if not so_match:
        return 2

    so_docstatus = [ row[1] for row in so_match if len(row) > 1 ]

    if 1 in so_docstatus:
        return 1
    if 0 in so_docstatus:
        return 0
    return 2


@frappe.whitelist()
def make_from_template(source_name, target_doc=None):
    return _make_from_template(source_name, target_doc)

def _make_from_template(source_name, target_doc, ignore_permissions=False):
    def postprocess(source, target):

        # Default mapping puts all child items of same doctype into the first matching table.
        # Instead, reset and separate according to parent field:
        target.items = []
        target.labour_travel = []

        for source_d in source.get('items', []):
            target_d = frappe.new_doc(source_d.doctype, target, 'items')
            map_doc(source_d, target_d, {}, source)
            target_d.idx = None
            target.append('items', target_d)

        for source_d in source.get('labour_travel', []):
            target_d = frappe.new_doc(source_d.doctype, target, 'labour_travel')
            map_doc(source_d, target_d, {}, source)
            target_d.idx = None
            target.append('labour_travel', target_d)

    doclist = get_mapped_doc("Service Report Template", source_name, {
            "Service Report Template": {
                "doctype": "Service Report",
                # "validation": {
                # 	"docstatus": ["=", 1]
                # }
                "field_no_map": [
                    'title', # Ignore template title
                ]
            },
            # "Service Report Item": {
            # 	"doctype": "Service Report Item",
            # 	"field_map": {
            # 		"parentfield": "parentfield",
            # 	},
            # },
        }, target_doc, postprocess, ignore_permissions=ignore_permissions)

    return doclist

@frappe.whitelist()
def make_sales_order(source_name, target_doc=None):
    return _make_sales_order(source_name, target_doc)

def _make_sales_order(source_name, target_doc, ignore_permissions=False):
    """ Map a Service Report to a Sales Order.

    If billed according to a quotation, the header (currency, exchange rates, price list, taxes, payment terms,
    discounts) is converted from the quotation like a native Quotation -> Sales Order conversion, and each item is
    linked to the quotation and takes the pricing of the matching quotation line (by item code). The quantities
    are those of the Service Report. Items that differ between the Service Report and the quotation are flagged.
    """

    sr = frappe.get_doc("Service Report", source_name)
    quotation = None
    quotation_lines = {}  # quotation_lines[item_code] = [Quotation Item, ...]
    unmatched = []  # item codes that are not on the quotation

    if sr.billing_basis == BILLING_QUOTATION and sr.quotation:
        quotation = frappe.get_doc("Quotation", sr.quotation)
        for line in quotation.items:
            quotation_lines.setdefault(line.item_code, []).append(line)

        if not target_doc:
            target_doc = _make_sales_order_from_quotation(quotation.name, ignore_permissions=ignore_permissions)
            # Items come from the Service Report
            target_doc.items = []
            target_doc.packed_items = []
            if target_doc.discount_amount:
                # The Service Report only bills part of the quotation
                add_warning(target_doc, _("The quotation has a discount of {0}, which was not applied. Please adjust manually.").format(
                    quotation.get_formatted("discount_amount")))
                target_doc.discount_amount = 0

    def update_item(obj, target, source_parent):
        if not quotation:
            return

        lines = quotation_lines.get(obj.item_code)
        if not lines:
            unmatched.append(obj.item_code)
            return

        # If an item is repeated on the quotation, use the lines in order
        line = lines[0]
        if len(lines) > 1:
            lines.pop(0)

        target.prevdoc_docname = quotation.name
        for fieldname in QUOTATION_PRICING_FIELDS:
            target.set(fieldname, line.get(fieldname))

    def set_missing_values(source, target):
        target.delivery_date = source.intervention_date
        target.ignore_pricing_rule = 1
        # target.flags.ignore_permissions = ignore_permissions

        for item in target.items:
            item.delivery_date = source.intervention_date

        if source.billing_basis == BILLING_SERVICE_AGREEMENT:
            for item in target.items:
                item.discount_percentage = 100

        target.run_method("set_missing_values")
        if quotation:
            target.run_method("calculate_taxes_and_totals")
            add_quotation_warnings(quotation, target, unmatched)

    doclist = get_mapped_doc("Service Report", source_name, {
            "Service Report": {
                "doctype": "Sales Order",
                "field_map": {
                    "intervention_date": "transaction_date",

                },
                "validation": {
                    "docstatus": ["=", 1]
                }
            },
            "Service Report Item": {
                "doctype": "Sales Order Item",
                "field_map": {
                    "parent": "service_report",
                },
                "condition": lambda item: item.qty > 0,
                "postprocess": update_item
            },
        }, target_doc, set_missing_values, ignore_permissions=ignore_permissions)

    return doclist

def add_quotation_warnings(quotation, sales_order, unmatched):
    """ Warn about quotation items that are not on the Service Report, and vice versa """

    on_sales_order = set(item.item_code for item in sales_order.items if item.prevdoc_docname == quotation.name)
    not_on_report = [
        "{0} {1}: {2} x {3} {4}".format(line.item_code, line.item_name, line.qty, quotation.currency, line.amount)
        for line in quotation.items if line.item_code not in on_sales_order
    ]

    if not_on_report:
        add_warning(sales_order, _("Items listed on quotation {0} but not on the Service Report:").format(quotation.name), not_on_report)
    if unmatched:
        add_warning(sales_order, _("Items not listed on quotation {0}, priced according to the price list:").format(quotation.name),
            [str(item_code) for item_code in unmatched])

def get_stock_levels(warehouse):
    data = frappe.db.sql("""
        SELECT
            item_code,
            actual_qty
        FROM `tabBin`
        WHERE warehouse = "{warehouse}"
    """.format(warehouse=warehouse), as_dict=True)

    return { row.item_code: row.actual_qty for row in data}

@frappe.whitelist()
def item_query(doctype, txt, searchfield, start, page_len, filters):
    warehouse = filters.get("warehouse")
    return frappe.db.sql("""
        SELECT
            it.item_code,
            CONCAT(ROUND(bin.actual_qty, 0), " ", bin.stock_uom, " in stock"),
            if(length(it.item_name) > 40, concat(substr(it.item_name, 1, 40), "..."), it.item_name) as item_name,
            if(length(it.description) > 40, concat(substr(it.description, 1, 40), "..."), it.description) as decription
        FROM `tabBin` bin
        JOIN `tabItem` it on it.item_code = bin.item_code
        WHERE bin.warehouse = "{warehouse}"
            AND bin.actual_qty > 0
            AND (it.item_code LIKE "%{txt}%" or it.item_name LIKE "%{txt}%")
            {match_conditions}
    """.format(txt=txt, warehouse=warehouse, match_conditions=get_match_cond(doctype)))


def update_status_from_sales_order(sales_order, method=None):
    # Called by hooks.py when a SO changes
    if not method in ('before_save', 'on_submit', 'on_cancel'):
        return

    for sr_name in list(set([it.service_report for it in sales_order.get("items")])):
        print("----------------------------------------")
        print(sr_name)
        print("----------------------------------------")
        if not sr_name:
            continue
        print("Updating service report", sr_name)
        doc = frappe.get_doc("Service Report", sr_name)
        doc.set_status()
