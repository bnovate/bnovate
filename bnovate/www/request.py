# Show data from a single request

import json
import frappe

from frappe import _
from frappe.utils import today
from frappe.exceptions import DoesNotExistError

from .helpers import auth, get_session_primary_customer, get_session_contact, get_addresses, allow_unstored_cartridges
from bnovate.bnovate.doctype.refill_request.refill_request import get_po_file

no_cache = 1


def get_context(context):
    auth(context)
    docname = frappe.form_dict.name 
    doc = get_request(docname) 

    if doc is None:
        raise DoesNotExistError

    context.doc = doc
    context.allow_unstored_cartridges = allow_unstored_cartridges()

    if doc.shipping_label:
        context.shipping_label_url = "/api/method/bnovate.www.request.get_label?name={name}".format(name=docname)

    po_file = get_po_file(docname)
    if po_file:
        context.po_file_name = po_file.file_name
        context.po_file_download_url = "/api/method/bnovate.www.request.download_po?name={name}".format(name=docname)

    context.form_dict = frappe.form_dict
    context.name = docname
    context.show_sidebar = True
    context.add_breadcrumbs = True
    context.parents = [
		{ "name": _("Refill Requests"), "route": "/requests" },
	]
    context.title = context.name
    return context


def get_request(name):
    # Return refill request, but only if it is for current customer
    primary_customer = get_session_primary_customer()


    doc = frappe.get_doc("Refill Request", name)
    if doc.customer != primary_customer.docname:
        return None
    doc.set_indicator()
    doc.set_tracking_url()

    return doc

@frappe.whitelist()
def get_label(name):
    """ Return shipping label for this Refill Request """
    doc = get_request(name)

    if doc is None or doc.shipping_label is None:
        raise DoesNotExistError()

    file_doc = frappe.get_doc("File", {"file_url": doc.shipping_label})

    frappe.local.response.filename = "shipping_label_{name}.pdf".format(name=name)
    frappe.local.response.filecontent = file_doc.get_content()
    frappe.local.response.type = "pdf"


@frappe.whitelist()
def attach_po():
    """ Attach an uploaded PO reference PDF to a Refill Request.

    Reached through /api/method/upload_file?method=bnovate.www.request.attach_po -
    that handler has already read the uploaded file into frappe.local before
    calling us (with no arguments), so we pull docname out of form_dict
    ourselves rather than taking it as a parameter.
    """
    docname = frappe.form_dict.docname
    doc = get_request(docname)
    if doc is None:
        raise DoesNotExistError()

    content = frappe.local.uploaded_file
    filename = frappe.local.uploaded_filename
    if not content or not filename:
        frappe.throw(_("No file was uploaded"))
    if not filename.lower().endswith(".pdf"):
        frappe.throw(_("Only PDF files are allowed"))

    file_doc = frappe.get_doc({
        "doctype": "File",
        "attached_to_doctype": "Refill Request",
        "attached_to_name": docname,
        "folder": "Home",
        "file_name": filename,
        "is_private": 1,
        "content": content,
    })
    file_doc.save(ignore_permissions=True)
    frappe.db.commit()

    return file_doc.file_url


@frappe.whitelist()
def download_po(name):
    """ Download the PO reference PDF attached to this Refill Request """
    doc = get_request(name)
    if doc is None:
        raise DoesNotExistError()

    po_file = get_po_file(name)
    if po_file is None:
        raise DoesNotExistError()

    file_doc = frappe.get_doc("File", po_file.name)

    frappe.local.response.filename = file_doc.file_name
    frappe.local.response.filecontent = file_doc.get_content()
    frappe.local.response.type = "download"


@frappe.whitelist()
def make_request(doc):
    """ Create a refill request """

    doc = frappe._dict(json.loads(doc))

    # Check that user does own the addresses
    valid_names = [a.name for a in get_addresses()]
    if not doc['shipping_address'] in valid_names:
        frappe.throw(_("You cannot order to this shipping address"), frappe.PermissionError)
    if not doc['billing_address'] in valid_names:
        frappe.throw(_("You cannot order to this billing address"), frappe.PermissionError)

    return_label_needed = doc['organize_return']
    parcel_count = int(doc['parcel_count']) if return_label_needed else 0


    new_request = frappe.get_doc({
        'doctype': 'Refill Request',
        'customer': get_session_primary_customer().docname,
        'contact_person': get_session_contact(),
        'transaction_date': today(),
        'shipping_address': doc['shipping_address'],
        'billing_address': doc['billing_address'],
        'shipping_address_display': doc['shipping_address_display'],
        'billing_address_display': doc['billing_address_display'],
        'items': doc['items'],  # using data.items calls the built-in dict function...
        'return_label_needed': return_label_needed,
        'parcel_count': parcel_count,
        'po_no': doc['po_no'],
        'remarks': doc['remarks'],
        'language': frappe.session.data.lang,
        'docstatus': 1,
    })

    new_request.insert(ignore_permissions=True)
    frappe.db.commit()

    return new_request