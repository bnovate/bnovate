""" Customisations for the Payment Reminder doctype (erpnextswiss) """

import frappe


@frappe.whitelist()
def attach_invoice_pdfs(docname):
    """ Attach a PDF of each invoice listed on a Payment Reminder to the reminder.

    Called before opening the email dialog (see public/js/doctype_includes/payment_reminder.js), which selects all
    attachments of the document. PDFs are generated with the invoice's default print format, in the language of the
    reminder. Invoices that are already attached are skipped.

    Returns the names of the files attached by this call.
    """

    doc = frappe.get_doc("Payment Reminder", docname)
    doc.check_permission("email")

    lang = doc.get("language") or frappe.db.get_value("Customer", doc.customer, "language") or frappe.local.lang

    existing = set(f.file_name for f in frappe.get_all("File", filters={
        "attached_to_doctype": "Payment Reminder",
        "attached_to_name": docname,
    }, fields=["file_name"]))

    attached = []
    for row in doc.sales_invoices:
        file_name = "{}.pdf".format(row.sales_invoice)
        if file_name in existing:
            continue
        frappe.get_doc({
            "doctype": "File",
            "file_name": file_name,
            "attached_to_doctype": "Payment Reminder",
            "attached_to_name": docname,
            "is_private": 1,
            "content": get_invoice_pdf(row.sales_invoice, lang),
        }).insert(ignore_permissions=True)
        existing.add(file_name)
        attached.append(file_name)

    return attached


def get_invoice_pdf(sinv_name, lang):
    """ Return PDF of the invoice, rendered in the given language """
    previous_lang = frappe.local.lang
    try:
        frappe.local.lang = lang
        return frappe.get_print("Sales Invoice", sinv_name, as_pdf=True)
    finally:
        frappe.local.lang = previous_lang
