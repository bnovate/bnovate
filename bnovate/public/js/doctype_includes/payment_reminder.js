/* Customisations for Payment Reminder
 *
 * Included by hooks.py to add client-side code to Payment Reminders
 *
 * - Shows envelope button for quick email (template: Payment Reminder Email Template in bNovate Settings, to the billing address of
 *   the most recent invoice). Attaches a PDF of each invoice first, the email dialog then selects all attachments.
 */

frappe.ui.form.on("Payment Reminder", {

    refresh(frm) {
        bnovate.utils.add_email_icon(frm, custom_email_dialog);
    },
});

async function custom_email_dialog(frm) {
    // Get email addresses from most recent invoice:
    const sinv_name = frm.doc.sales_invoices.slice(-1)[0]?.sales_invoice;
    if (!sinv_name) {
        frappe.throw(__('No invoice found to get billing address from'));
        return;
    }

    const sinv = await frappe.db.get_doc("Sales Invoice", sinv_name);
    const addr = await frappe.db.get_doc("Address", sinv.customer_address); // billing addr
    const recipients = Array.from(new Set([addr.email_id || '', sinv.email || '', sinv.email_id || '', sinv.contact_email || ''].filter(i => i))).join(', ');

    const template_name = await bnovate.utils.get_setting('payment_reminder_template') || "Payment Reminder";

    await attach_invoices(frm);

    return bnovate.utils.email_dialog(frm, template_name, { recipients });
}

// Attach a PDF of each invoice to this document (backend avoid duplicates)
async function attach_invoices(frm) {
    const dlg = frappe.show_progress(__("Attaching invoices..."), 33, 100, __("Please wait."));
    try {
        await frappe.call({
            method: 'bnovate.bnovate.utils.payment_reminder.attach_invoice_pdfs',
            args: { docname: frm.doc.name },
        });
        // Refresh attachment list, so the email dialog sees the new files
        await new Promise(resolve => frm.sidebar.reload_docinfo(resolve));
    } finally {
        dlg.hide();
    }
}
