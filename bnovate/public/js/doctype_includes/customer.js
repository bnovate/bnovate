/* Customisations for Customer
 * 
 * Included by hooks.py to add client-side code to Sales Invoices
 * (same effect as writing a custom script)
 */

frappe.ui.form.on("Customer", {
    before_load(frm) {
        frm.dashboard.add_transactions({
            'items': ['Subscription Contract', 'Connectivity Package', 'Refill Request', 'Blanket Order', 'Serial No', 'License Key'],
            'label': 'Orders',
        })
        frm.dashboard.add_transactions({
            'items': ['Service Report'],
            'label': 'Support',
        })
        frm.dashboard.add_transactions({
            'items': ['Sales Proposal'],
            'label': __('Pre Sales'),  // the group of the Quotations
        })
    },
    setup(frm) {
        frm.set_query('portal_billing_address', function (doc) {
            return {
                query: 'frappe.contacts.doctype.address.address.address_query',
                filters: {
                    link_doctype: 'Customer',
                    link_name: doc.name
                }
            };
        })
    },
    refresh(frm) {
        frm.add_custom_button(__("Stored Cartridges"), function () {
            frappe.route_options = { customer: frm.doc.name, only_stored: true };
            frappe.set_route("query-report", "Cartridge Status");
        }, __("View"));

        frm.add_custom_button(__("Owned Serial Numbers"), function () {
            frappe.route_options = { owned_by: frm.doc.name };
            frappe.set_route("List", "Serial No");
        }, __("View"));

        frm.add_custom_button(__("Shipments"), function () {
            frappe.route_options = { customer: frm.doc.name };
            frappe.set_route("query-report", "Shipment Report");
        }, __("View"));

        frm.add_custom_button(__("Orders Awaiting Call-Off"), function () {
            frappe.route_options = {
                customer: frm.doc.name,
                status: ["Draft", "To Deliver", "To Deliver and Bill"],
                from_date: frappe.datetime.year_end(),
                to_date: frappe.datetime.year_end(),
                filter_on_date: "delivery_date"
            };
            frappe.set_route("query-report", "Item-wise Sales History (bN)");
        }, __("View"));
    },
    check_vat(frm) {
        bnovate.utils.check_vat_number(frm.doc.tax_id);
    },
    check_eori(frm) {
        bnovate.utils.check_eori(frm.doc.eori_number);
    }
})