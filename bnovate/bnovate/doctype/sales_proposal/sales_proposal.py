# -*- coding: utf-8 -*-
# Copyright (c) 2026, bnovate, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import html
import json
import os

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, formatdate, fmt_money
from erpnext.accounts.party import set_address_details, set_contact_details
from erpnext.controllers.queries import get_match_cond



class SalesProposal(Document):
    """ The documents we send to a customer to win a deal: cover page, cover letter, quotations, appendices...

    The PDF is assembled by utils/sales_proposal_pdf.py, the cover letter is written by utils/ai.py.
    """

    def onload(self):
        """ Current status of the linked quotations, for the indicator of the table. It is not stored in the proposal: it
        changes whenever the quotation does (ordered, expired...). """
        names = [row.quotation for row in self.quotations if row.quotation]
        if names:
            self.set_onload("quotation_status", {q.name: q for q in frappe.get_all(
                "Quotation", filters={"name": ["in", names]}, fields=["name", "status", "docstatus", "valid_till"])})

    def validate(self):
        if not self.title:
            self.title = self.customer_name

        self.validate_quotations()
        self.validate_appendices()

    def validate_appendices(self):
        for row in self.appendices:
            if not (row.file or "").lower().endswith(".pdf"):
                frappe.throw(_("Row {0}: the appendix must be a PDF file.").format(row.idx))
            row.title = (row.title or os.path.splitext(os.path.basename(row.file))[0]).strip()

    def validate_quotations(self):
        listed = set()
        for row in self.quotations:
            if row.quotation in listed:
                frappe.throw(_("Row {0}: quotation {1} is listed more than once.").format(row.idx, row.quotation))
            listed.add(row.quotation)

            if frappe.db.get_value("Quotation", row.quotation, "docstatus") == 2:
                frappe.throw(_("Row {0}: quotation {1} is cancelled.").format(row.idx, row.quotation))


def get_key_products(quotation):
    """ The key products of a quotation: its items that have a commercial description, once each, in the order of the quotation.

    Return a list of dicts: item_code, item_name (as on the quotation: in the language of the quotation), description (the
    commercial description, in the language of the item master) and image.
    """
    rows = frappe.db.sql("""
        SELECT qi.item_code, COALESCE(NULLIF(qi.item_name, ''), item.item_name) AS item_name, item.commercial_description, item.image
        FROM `tabQuotation Item` qi
        JOIN `tabItem` item ON item.name = qi.item_code
        WHERE qi.parent = %s AND qi.parenttype = 'Quotation' AND IFNULL(item.commercial_description, '') != ''
        ORDER BY qi.idx
    """, quotation, as_dict=True)

    products, seen = [], set()
    for row in rows:
        if row.item_code not in seen:
            seen.add(row.item_code)
            products.append(frappe._dict(
                item_code=row.item_code, item_name=html.unescape(row.item_name or ""), description=row.commercial_description.strip(), image=row.image))
    return products

@frappe.whitelist()
def get_proposals_of_quotation(quotation):
    """ Names of the Sales Proposals that list this quotation, most recent first. For the dashboard of the Quotation. """
    return [p.name for p in frappe.get_list(
        "Sales Proposal",
        filters=[["Sales Proposal Quotation", "quotation", "=", quotation]],
        fields=["name"], order_by="modified desc", distinct=True,
    )]


@frappe.whitelist()
def get_customer_details(customer):
    """ Defaults of a new proposal for this customer: name, language, address and contact.

    The address and the contact are picked by the helpers that ERPNext uses for a Quotation, so that a proposal and its
    quotations start from the same ones.
    """
    customer = frappe.get_doc("Customer", customer)
    customer.check_permission("read")

    details = frappe._dict()
    set_address_details(details, customer, "Customer")
    set_contact_details(details, customer, "Customer")

    return {
        "customer_name": customer.customer_name,
        "language": customer.language,
        "customer_address": details.customer_address,
        "address_display": details.address_display or "",
        "contact_person": details.contact_person,
        "contact_display": details.contact_display or "",
        "contact_mobile": details.contact_mobile or "",
        "contact_email": details.contact_email or "",
    }


@frappe.whitelist()
def quotation_query(doctype, txt, searchfield, start, page_len, filters):
    """ Search for the Linked Quotations table.

    Quotations of the customer, most recent first. The text is looked for in the number and title of the quotation,
    in the customer name, and in the code and name of its items. Cancelled quotations are left out.
    """
    if isinstance(filters, str):
        filters = json.loads(filters)
    customer = (filters or {}).get("customer")

    values = {"txt": "%{0}%".format(txt or ""), "start": cint(start), "page_len": cint(page_len)}
    customer_condition = ""
    if customer:
        customer_condition = "and `tabQuotation`.quotation_to = 'Customer' and `tabQuotation`.party_name = %(customer)s"
        values["customer"] = customer

    rows = frappe.db.sql("""
        select
            `tabQuotation`.name, `tabQuotation`.title, `tabQuotation`.transaction_date,
            `tabQuotation`.status, `tabQuotation`.currency, `tabQuotation`.grand_total
        from `tabQuotation`
        where `tabQuotation`.docstatus < 2
            {customer_condition}
            and (
                `tabQuotation`.name like %(txt)s
                or `tabQuotation`.title like %(txt)s
                or `tabQuotation`.customer_name like %(txt)s
                or exists (
                    select 1 from `tabQuotation Item`
                    where `tabQuotation Item`.parent = `tabQuotation`.name
                        and (`tabQuotation Item`.item_code like %(txt)s or `tabQuotation Item`.item_name like %(txt)s)
                )
            )
            {match_conditions}
        order by `tabQuotation`.transaction_date desc, `tabQuotation`.creation desc
        limit %(start)s, %(page_len)s
    """.format(customer_condition=customer_condition, match_conditions=get_match_cond("Quotation")), values, as_dict=True)

    return [
        (row.name, row.title, " · ".join(filter(None, [
            formatdate(row.transaction_date), row.status, fmt_money(row.grand_total, currency=row.currency),
        ])))
        for row in rows
    ]
