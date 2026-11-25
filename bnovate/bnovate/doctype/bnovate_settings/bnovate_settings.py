# -*- coding: utf-8 -*-
# Copyright (c) 2023, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document

from bnovate.bnovate.utils.permissions import is_desk_user


class bNovateSettings(Document):
    pass



@frappe.whitelist()
def get_whitelisted_setting(key):
    """ Return a setting that is whitelisted for use by the front-end.
 
    Only allowed for Desk users.
 
    Used by bnovate.utils.get_setting() in the browser. """

    WHITELISTED_SETTINGS = (
        "so_template",
        "dn_template",
        "sinv_template",
        "payment_reminder_template",
        "sales_proposal_template",
        "qc_workstation",
    )

    if not is_desk_user():
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    if key not in WHITELISTED_SETTINGS:
        frappe.throw(_("The setting {0} is not available.").format(key), frappe.PermissionError)
    return frappe.db.get_single_value("bNovate Settings", key)
