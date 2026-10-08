""" Make Service Reports searchable in the global search, by name and serial number.

The list of searchable doctypes is stored in Global Search Settings, it is not updated from hooks on migrate.
"""

import frappe
from frappe.utils.global_search import rebuild_for_doctype


def execute():
    # Patches run before doctypes are synced, we need the new searchable field
    frappe.reload_doc("bnovate", "doctype", "service_report")

    settings = frappe.get_single("Global Search Settings")
    if "Service Report" not in [d.document_type for d in settings.allowed_in_global_search]:
        settings.append("allowed_in_global_search", {"document_type": "Service Report"})
        settings.save(ignore_permissions=True)

    frappe.cache().delete_value("doctypes_with_global_search")
    rebuild_for_doctype("Service Report")
