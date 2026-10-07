/* Customisations for Payment Reminder
 *
 * Included by hooks.py to add client-side code to Payment Reminders
 *
 * - Shows envelope button for quick email. Attaches a PDF of each invoice first, the email dialog then selects all
 *   attachments.
 */

frappe.ui.form.on("Payment Reminder", {

    async refresh(frm) {
        // Add envelope icon to send email
        if (frm.doc.docstatus === 1) {

            // Get billing email address from most recent invoice:

            const sinv_name = frm.doc.sales_invoices.slice(-1)[0]?.sales_invoice;
            if (sinv_name) {
                const sinv = await frappe.db.get_doc("Sales Invoice", sinv_name);
                const addr = await frappe.db.get_doc("Address", sinv.customer_address);
                frm.doc.email_id = addr.email_id;
                frm.page.add_action_icon(__("fa fa-envelope-o"), function () {
                    email_reminder(frm);
                });
            }
        }
    },
});

async function email_reminder(frm) {
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
    bnovate.utils.email_dialog(frm, "Payment Reminder");
}
