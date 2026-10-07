""" Identify invoice lines that require deferred revenue.

bNovate does not use the ERPNext deferred revenue accounting (enable_deferred_revenue ticked on the
line, booking into the deferred revenue account). Revenue is booked normally and deferrals are computed
separately by accounting. We only flag the lines and record the service period, using the standard
service start / end / stop date fields.
"""

import frappe
from frappe import _
from frappe.utils import add_months, getdate


def set_deferral_flags(doc, method=None):
    """ Called on Sales Invoice before_validate hook. Makes sure bn_requires_deferral is set based on item code.

    - Line flag follows the item (also done by fetch_from in the UI, repeated here for invoices created server-side).
    - Default service period if missing: starts at posting date, lasts the number of months defined on the item.
    - Credit notes keep the dates of the lines they refund.
    """

    item_codes = list(set(it.item_code for it in doc.items if it.item_code))
    items = {}
    if item_codes:
        items = {it.name: it for it in frappe.get_all(
            "Item",
            filters={"name": ["in", item_codes]},
            fields=["name", "bn_requires_deferral", "no_of_months"],
        )}

    for line in doc.items:
        if line.item_code in items:
            line.bn_requires_deferral = items[line.item_code].bn_requires_deferral

    if doc.is_return:
        return

    for line in doc.items:
        if not line.bn_requires_deferral:
            continue
        if not line.service_start_date:
            line.service_start_date = doc.posting_date
        if not line.service_end_date:
            no_of_months = items[line.item_code].no_of_months
            if not no_of_months:
                frappe.throw(_("Row {0}: {1} requires deferred revenue. Please set the Service End Date.").format(line.idx, line.item_code))
            line.service_end_date = add_months(line.service_start_date, no_of_months)
        if getdate(line.service_end_date) < getdate(line.service_start_date):
            frappe.throw(_("Row {0}: Service End Date cannot be before Service Start Date.").format(line.idx))
