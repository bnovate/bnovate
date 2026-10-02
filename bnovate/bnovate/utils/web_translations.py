# (c) 2026, bNovate
from __future__ import unicode_literals

import os

import frappe
from frappe.translate import get_messages_from_file, make_dict_from_messages


def get_portal_translated_dict():
    """ Translations for strings in portal scripts that frappe doesn't scan.

    The portal loads its JS translations from the files listed in web_include_js
    only (see frappe.translate.get_messages_from_include_files). The wizard and
    form modals are loaded on demand with frappe.require, and some pages call
    __() from inline scripts, so their strings would otherwise stay in English.
    Hooked on get_translated_dict for ("boot", None).
    """
    messages = []
    for folder, extension in ((("public", "js", "web_includes"), ".js"), (("www",), ".html")):
        base = frappe.get_app_path("bnovate", *folder)
        for filename in sorted(os.listdir(base)):
            if filename.endswith(extension):
                messages.extend(get_messages_from_file(os.path.join(base, filename)))

    # Status labels of the cartridge list are defined in the report, not in the page. The page
    # translates them client side, with __().
    messages.extend(get_messages_from_file(
        frappe.get_app_path("bnovate", "bnovate", "report", "cartridge_status", "cartridge_status.py")))

    return make_dict_from_messages(messages)
