# (c) 2026, bNovate and contributors
#
# Utility functions to apply permission checks.

import frappe


def is_guest():
    if frappe.session.user=='Administrator':
        return False
    if frappe.session.user=='Guest' or not "@" in frappe.session.user:
        return True
    return False

def is_desk_user():
    """ Return True if current user has access to Desk """
    if frappe.session.user=='Administrator':
        return True
    if is_guest():
        return False
    user_type = frappe.db.get_value("User", {"name": frappe.session.user}, "user_type")
    if user_type == "System User":
        return True
    return False

def is_system_user():
    return is_desk_user()