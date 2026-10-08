""" Improvements to the global search """

import re

import frappe
from frappe.desk.doctype.global_search_settings.global_search_settings import get_doctypes_for_global_search
from frappe.utils.global_search import search as frappe_search

# Looks like a document name: letters, a dash, digits (SR-00029, SO-00681-1)
NAME_PATTERN = re.compile(r"^[A-Za-z]+-\d+(-\d+)?$")
MAX_NAME_MATCHES = 10


@frappe.whitelist()
def search(text, start=0, limit=20, doctype=""):
    """ Frappe's global search, with documents whose name starts with the search text listed first.

    The full text index ignores short words, so "SR-00029" is searched as "00029", which matches documents of
    all doctypes with that number, and the one we are looking for is easily cut off by the result limit.
    """

    results = frappe_search(text, start=start, limit=limit, doctype=doctype)

    text = (text or "").strip()
    if int(start) > 0 or not NAME_PATTERN.match(text):
        return results

    doctypes = get_doctypes_for_global_search()
    if doctype:
        doctypes = [dt for dt in doctypes if dt == doctype]
    if not doctypes:
        return results

    matches = frappe.db.sql("""
        SELECT `doctype`, `name`, `content`
        FROM `__global_search`
        WHERE `name` LIKE %(name)s AND `doctype` IN ({doctypes})
        LIMIT {max_matches}
    """.format(
        doctypes=", ".join(frappe.db.escape(dt) for dt in doctypes),
        max_matches=MAX_NAME_MATCHES,
    ), {"name": frappe.db.escape(text, percent=False)[1:-1] + "%"}, as_dict=True)

    matches = [m for m in matches if frappe.has_permission(m.doctype, "read", doc=m.name)]
    matches.sort(key=lambda m: (doctypes.index(m.doctype), m.name))
    for m in matches:
        m.rank = 1.0

    found = set((m.doctype, m.name) for m in matches)
    return (matches + [r for r in results if (r.doctype, r.name) not in found])[:int(limit)]
