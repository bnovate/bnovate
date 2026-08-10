/*
Supplier Script
--------------------

What this does:
* Adds Blanket orders to the dashboard
* Manages supplier approvals

*/

frappe.ui.form.on('Supplier', {

    before_load(frm) {
        frm.dashboard.add_transactions([{
            'items': ['Blanket Order'],
            'label': 'Procurement'
        }])
    },

    async validate(frm) {

        // Check changes to financial information. Warning: get_doc will update cache and erase local changes!
        const resp = await frappe.db.get_value(frm.doc.doctype, frm.doc.name, ['iban', 'esr_participation_number', 'default_payment_method']);
        const upstream_doc = resp.message || null;

        if (upstream_doc) {
            if (
                (upstream_doc.iban && upstream_doc.iban !== frm.doc.iban) ||
                (upstream_doc.esr_participation_number && upstream_doc.esr_participation_number !== frm.doc.esr_participation_number) ||
                (upstream_doc.default_payment_method && upstream_doc.default_payment_method !== frm.doc.default_payment_method)
            ) {
                let confirmed = await bnovate.utils.confirm_dialog("Detected changes to payment information. Approvals will be reset. Do you want to continue?");

                if (!confirmed) {
                    frappe.validated = false;
                }

                frm.clear_table('approvals');
            }
        }
    },

    async approve(frm) {
        let open_approval = frm.doc.approvals?.find(a => !a.timestamp_revoked && a.user === frappe.session.user);

        if (open_approval) {
            frappe.throw(__('You have already approved this supplier.'))
        }

        // Check if user is autorized to approve this doctype.
        const permissions_doc = await frappe.db.get_doc('Approval Permissions');
        const has_permission = permissions_doc.permissions.find(p => p.user === frappe.session.user && p.for_doctype === 'Supplier');

        if (!has_permission) {
            frappe.throw(__('You are not authorized to approve suppliers.'))
        }

        let row = frm.add_child('approvals');
        row.user = frappe.session.user;
        row.timestamp_approved = frappe.datetime.now_datetime();
        frm.refresh_field('approvals');
        frm.save();
    },

    revoke(frm) {
        let open_approval = frm.doc.approvals.find(a => !a.timestamp_revoked && a.user === frappe.session.user);
        if (open_approval) {
            open_approval.timestamp_revoked = frappe.datetime.now_datetime();
            frm.refresh_field('approvals');
            frm.save();
        }
    }

});