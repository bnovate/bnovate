/* Customisations for Sales Invoice
 * 
 * Included by hooks.py to add client-side code to Sales Invoices
 * (same effect as writing a custom script)
 * 
 * - Shows Subscription Contract in dashboard
 * - Removes legacy Create Subscription action
 */

frappe.ui.form.on("Sales Invoice", {
    before_load(frm) {
        frm.dashboard.add_transactions({
            'items': ['Subscription Contract'],
            'label': 'Subscription',
        })
        frm.dashboard.data.internal_links['Subscription Contract'] = ['items', 'subscription'];
    },
    refresh(frm) {
        setTimeout(() => {
            frm.remove_custom_button("Subscription", "Create")
        }, 500);

        frm.add_custom_button(__('Deferred Revenue Entries'), async function () {
            await bnovate.utils.book_deferred_income_or_expense(frm.doc.doctype, frm.doc.name);
        }, __('Create'))


    },
})

frappe.ui.form.on("Sales Invoice Item", {
    // Flag is fetched from the item. Start the service period at the posting date by default;
    // ERPNext's own service_start_date handler then fills the end date from the item's number of months.
    bn_requires_deferral(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.bn_requires_deferral && !row.service_start_date && !frm.doc.is_return) {
            frappe.model.set_value(cdt, cdn, "service_start_date", frm.doc.posting_date);
        }
    },
})