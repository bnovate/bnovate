""" Move the "requires deferred revenue" identification from the ERPNext deferral flags to bn_requires_deferral.

- Items flagged enable_deferred_revenue get bn_requires_deferral instead (and the ERPNext flag is cleared, so new
  invoices neither book into the deferred revenue account nor show the ERPNext deferral fields).
- Existing invoices are not touched. Their ERPNext flag keeps recognising the deferred revenue already booked
  until it has run out.
"""

import frappe
from frappe.modules.utils import sync_customizations


def execute():
    # Patches run before customizations are synced, but we need the new fields
    sync_customizations("bnovate")
    frappe.db.commit()

    frappe.db.sql("""
        UPDATE `tabItem` SET bn_requires_deferral = 1, enable_deferred_revenue = 0
        WHERE enable_deferred_revenue = 1""")
