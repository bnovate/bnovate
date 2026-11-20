# -*- coding: utf-8 -*-
# Copyright (c) 2026, bnovate, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import html
import json
import os
import re
from contextlib import contextmanager

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, formatdate, fmt_money
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


EXPENSE_CATEGORIES = ("CAPEX", "OPEX")  # in the order of the columns of the table. The category "Ignore" is left out.


def get_cost_groups(quotation):
    """ The lines of a quotation grouped by section and by customer expense category, with the subtotal of each group.

    A section starts at a line that has a "section header" (the line "A) Purchase of the instrument..."), and goes on until
    the next one. Subtotals are the net amounts of the lines (after discounts, before taxes), as quoted.

    Return {"currency": "CHF",
            "rows": [{"group_id": 1, "group": "A) Purchase...", "customer_expense_category": "CAPEX", "item_names": [...], "total": 73000.0}, ...],
            "unclassified": [{"group": ..., "item_names": [...], "total": ...}]}
    The rows are in the order of the quotation, CAPEX before OPEX in a section. Lines of category "Ignore" are left out. Lines
    that have no category are listed apart if they have an amount: the table can not place them. A line whose own category is
    blank (an old quotation, a line added before the categories) takes the category of its item, else of the group of the item.
    """
    lines = frappe.db.sql("""
        SELECT COALESCE(NULLIF(qi.item_name, ''), item.item_name) AS item_name, qi.section_header, qi.net_amount,
            COALESCE(NULLIF(qi.customer_expense_category, ''), NULLIF(item.customer_expense_category, ''), NULLIF(grp.customer_expense_category, ''), '')
                AS customer_expense_category
        FROM `tabQuotation Item` qi
        LEFT JOIN `tabItem` item ON item.name = qi.item_code
        LEFT JOIN `tabItem Group` grp ON grp.name = item.item_group
        WHERE qi.parent = %s AND qi.parenttype = 'Quotation'
        ORDER BY qi.idx
    """, quotation, as_dict=True)

    sections = []  # [{"group": header, "CAPEX": {...}, "OPEX": {...}, "": {...}}]
    for line in lines:
        header = html.unescape(line.section_header or "").strip()
        if header or not sections:
            sections.append({"group": header or None})
        section = sections[-1]

        category = line.customer_expense_category or ""
        if category == "Ignore":
            continue
        if category not in EXPENSE_CATEGORIES and not flt(line.net_amount):
            continue  # a free line without category (a free accessory): nothing to place
        entry = section.setdefault(category, {"item_names": [], "total": 0.0})
        name = html.unescape(line.item_name or "").strip()
        if name and name not in entry["item_names"]:
            entry["item_names"].append(name)
        entry["total"] += flt(line.net_amount)

    rows, unclassified = [], []
    for group_id, section in enumerate(sections, 1):
        for category in EXPENSE_CATEGORIES:
            if category in section:
                rows.append({"group_id": group_id, "group": section["group"], "customer_expense_category": category,
                             "item_names": section[category]["item_names"], "total": flt(section[category]["total"], 2)})
        if "" in section:
            unclassified.append({"group": section["group"], "item_names": section[""]["item_names"], "total": flt(section[""]["total"], 2)})

    return {"currency": frappe.db.get_value("Quotation", quotation, "currency"), "rows": rows, "unclassified": unclassified}


@contextmanager
def _language(lang):
    previous = frappe.local.lang
    frappe.local.lang = lang or previous
    try:
        yield
    finally:
        frappe.local.lang = previous


def get_cost_column_titles(lang=None):
    """ Titles of the columns of the cost table: the customer reads "initial investment" and "running costs", not CAPEX and OPEX. """
    with _language(lang):
        return {"CAPEX": _("Initial investment"), "OPEX": _("Running costs")}


# The heading row is made of <td>, not <th>/<thead>: the Text Editor of the form does not know those and merges the row into one cell.
# Jinja does not escape by itself: every text is passed through | e.
COST_TABLE_TEMPLATE = """
{% macro amount(value) %}{% if value %}{{ money(value) | e }}{% else %}&ndash;{% endif %}{% endmacro %}
{% if explanation %}<p>{{ explanation | e }}</p>{% endif %}
<table style="width: 100%; border-collapse: collapse;">
    <tbody>
        <tr>
            <td style="{{ head_style }} text-align: left;"><strong>{{ _("Description") | e }}</strong></td>
            {% for title in column_titles %}
            <td style="{{ head_style }} text-align: right;"><strong>{{ title | e }}</strong></td>
            {% endfor %}
        </tr>
        {% for line in lines %}
        <tr>
            <td style="{{ cell_style }}">{{ line.description | e }}</td>
            {% for category in categories %}
            <td style="{{ cell_style }} text-align: right;">{{ amount(line[category]) }}</td>
            {% endfor %}
        </tr>
        {% endfor %}
        <tr>
            <td style="{{ cell_style }}"><strong>{{ _("Total") | e }}</strong></td>
            {% for category in categories %}
            <td style="{{ cell_style }} text-align: right;"><strong>{{ amount(totals[category]) }}</strong></td>
            {% endfor %}
        </tr>
    </tbody>
</table>
<p><em>{{ _("Amounts are as quoted, before taxes.") | e }}</em></p>
"""


def render_cost_table(cost_groups, descriptions, explanation="", lang=None):
    """ HTML of the cost simulation: the explanation, then a table with a line for each section of the quotation.

    The amounts come from the calculation (get_cost_groups), never from the AI, which only writes the descriptions and the
    explanation. descriptions: {group_id: text}. Texts are plain text. The HTML is made by COST_TABLE_TEMPLATE.
    """
    categories = ["CAPEX", "OPEX"]
    by_group, totals = {}, {category: 0.0 for category in categories}
    for row in cost_groups["rows"]:
        group = by_group.setdefault(row["group_id"], dict.fromkeys(categories, 0.0))
        group["description"] = descriptions.get(row["group_id"]) or row["group"] or ", ".join(row["item_names"])
        group[row["customer_expense_category"]] += row["total"]
        totals[row["customer_expense_category"]] += row["total"]

    with _language(lang):
        titles = {"CAPEX": _("Initial investment"), "OPEX": _("Running costs")}
        rendered = frappe.render_template(COST_TABLE_TEMPLATE, {
            "explanation": (explanation or "").strip(),
            "categories": categories,
            "column_titles": [titles[category] for category in categories],
            "lines": list(by_group.values()),
            "totals": totals,
            "money": lambda value: fmt_money(value, currency=cost_groups["currency"]),
            "cell_style": "padding: 4px 8px; border-bottom: 1px solid #d1d8dd;",
            "head_style": "padding: 4px 8px; border-bottom: 2px solid #333;",
        })
    return re.sub(r">\s+<", "><", rendered).strip()


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
