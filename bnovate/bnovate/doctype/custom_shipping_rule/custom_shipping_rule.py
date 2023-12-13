# -*- coding: utf-8 -*-
# Copyright (c) 2023, bnovate, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import json
import frappe, erpnext
from frappe import _, msgprint, throw
from frappe.utils import flt, fmt_money
from frappe.model.document import Document
from erpnext.accounts.doctype.shipping_rule.shipping_rule import ShippingRule


class CurrencyMismatchError(frappe.ValidationError): pass

class CustomShippingRule(ShippingRule):

    def apply(self, doc):
        '''Apply shipping rule on given doc. Called from accounts controller'''

        shipping_amount = 0.0
        by_value = False

        self.validate_countries(doc)

        if self.calculate_based_on == 'Net Total':
            value = doc.base_net_total
            by_value = True

        elif self.calculate_based_on == 'Net Weight':
            value = doc.total_net_weight
            by_value = True

        elif self.calculate_based_on == 'Fixed':
            shipping_amount = self.shipping_amount

        # shipping amount by value, apply conditions
        if by_value:
            shipping_amount = self.get_shipping_amount_from_rules(value)

        # convert to order currency
        if doc.currency != self.currency:
            throw(_("Shipping rule currency does not match document currency"), CurrencyMismatchError)

            # shipping_amount = flt(shipping_amount / doc.conversion_rate, 2)

        self.add_shipping_rule_to_tax_table(doc, shipping_amount)


@frappe.whitelist()
def apply_rule(doc):
    """ Applies shipping rule to a document. 
    
    This method reimplements native functions of the AccountsController that
    would be called through run_method.
    """
    doc = frappe.get_doc(json.loads(doc))	
    doc._original_modified = doc.modified
    doc.check_if_latest()

    if doc.custom_shipping_rule:
        shipping_rule = frappe.get_doc("Custom Shipping Rule", doc.custom_shipping_rule)
        shipping_rule.apply(doc)
        doc.calculate_taxes_and_totals()

    # frappe.response.message = ''
    frappe.response.docs.append(doc)