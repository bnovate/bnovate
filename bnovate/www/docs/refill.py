# Documentation: how to order a refill. Public, like the Help page it sits under.

import frappe

from frappe import _

no_cache = 1

# Screenshots exist in these languages, see public/img/docs/refill/
DOC_LANGUAGES = ("en", "fr", "de")


def get_context(context):
    lang = frappe.local.lang if frappe.local.lang in DOC_LANGUAGES else "en"
    context.img_dir = "/assets/bnovate/img/docs/refill/{0}".format(lang)

    context.title = _("How to order a refill")
    context.add_breadcrumbs = True
    context.parents = [
        {"name": _("Help"), "route": "/docs"},
    ]
    return context
