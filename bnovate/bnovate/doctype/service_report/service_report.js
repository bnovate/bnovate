// Copyright (c) 2023, bnovate, libracore and contributors
// For license information, please see license.txt

{% include 'erpnext/selling/sales_common.js' %}

frappe.provide('bnovate.service_report');

const CHANNEL_DIRECT = 'Direct';
const CHANNEL_PARTNER = 'Service Partner';
const BILLING_PARTNER = 'Through Service Partner';
const BILLING_QUOTATION = 'According to Quotation';
const INTERVENTION_UPGRADE = 'Software Upgrade';

frappe.ui.form.on('Service Report', {
	onload(frm) {

		// Setup queries

		// contact_query from erpnext uses frappe.dynamic_link to set filters...
		// frappe.dynamic_link = { doc: frm.doc, fieldname: 'customer', doctype: 'Customer' }
		// frm.set_query('contact_person', erpnext.queries.contact_query);
		frm.set_query('contact_person', function () {
			return {
				// contact_query from frappe package is more flexible than the one from erpnext
				query: 'frappe.contacts.doctype.contact.contact.contact_query',
				filters: {
					link_doctype: 'Customer',
					link_name: frm.doc.customer,
				}
			}
		});

		frm.set_query('service_partner', function () {
			return {
				filters: {
					is_service_partner: 1,
				}
			}
		});

		frm.set_query('technician', function () {
			return {
				query: 'frappe.contacts.doctype.contact.contact.contact_query',
				filters: {
					link_doctype: 'Customer',
					link_name: frm.doc.service_partner,
				}
			}
		});

		frm.set_query("quotation", function () {
			return {
				filters: {
					party_name: frm.doc.customer,
				}
			}
		});
		frm.set_query("subscription", function () {
			return {
				filters: {
					customer: frm.doc.customer,
					status: "Active",
					serial_no: frm.doc.serial_no,
				}
			}
		});
		frm.set_query("quotation", function () {
			return {
				filters: {
					party_name: frm.doc.customer,
				}
			}
		});
		frm.set_query("serial_no", function () {
			return {
				filters: {
					item_group: "Instruments",
					owned_by: frm.doc.customer,
				}
			}
		});
		frm.set_query("set_warehouse", function () {
			return {
				filters: {
					company: frm.doc.company,
					is_group: 0,
				}
			}
		});

		frm.set_query("item_code", "items", function (doc, cdn, cin) {
			const warehouse = frappe.get_doc(cdn, cin).warehouse || frm.doc.set_warehouse;

			if (warehouse) {
				return {
					query: "bnovate.bnovate.doctype.service_report.service_report.item_query",
					filters: {
						warehouse
					}
				}
			}

		});

		frm.set_query("warehouse", "items", function () {
			return {
				filters: {
					company: frm.doc.company,
					is_group: 0,
				}
			}
		});
	},

	refresh(frm) {
		if (frm.doc.status === 'To Bill') {
			frm.add_custom_button(__("Sales Order"), () => {
				frappe.model.open_mapped_doc({
					method: "bnovate.bnovate.doctype.service_report.service_report.make_sales_order",
					frm: cur_frm,
					// Link triggers fetch the current price list rates. When billing according to a quotation, the prices
					// come from the quotation (like a native Quotation -> Sales Order) and must not be overwritten.
					run_link_triggers: !(frm.doc.billing_basis === BILLING_QUOTATION && frm.doc.quotation),
				});
			}, __("Create"));

			frm.add_custom_button(__("Ignore Billing"), () => {
				frm.doc.ignore_billing = 1;
				frm.save("Update");
				frappe.show_alert({ message: __("Billing skipped"), indicator: 'green' });
			}, __("Status"));

		}
	},

	channel(frm) {
		frm.toggle_reqd('bnovate_technician', frm.doc.channel === CHANNEL_DIRECT);
		frm.toggle_reqd('service_partner', frm.doc.channel === CHANNEL_PARTNER);
		if (frm.doc.channel == 'Service Partner') {
			frm.set_value('billing_basis', BILLING_PARTNER);
		} else {
			frm.set_value('billing_basis', null);
		}
	},

	async bnovate_technician(frm) {
		console.log(frm.doc)
		const resp = await frappe.db.get_value("Warehouse", { for_user: frm.doc.bnovate_technician }, 'name');
		frm.set_value('set_warehouse', resp.message?.name);
		frm.run_link_triggers('set_warehouse');
	},

	async technician(frm) {
		let technician_display = null;
		if (frm.doc.technician) {
			technician_display = await bnovate.utils.get_contact_display(frm.doc.technician);
		}
		frm.set_value('technician_name', technician_display);
	},

	reason_for_visit(frm) {
		frm.toggle_reqd('description', frm.doc.reason_for_visit !== INTERVENTION_UPGRADE);
		frm.toggle_reqd('resolution', frm.doc.reason_for_visit === 'Service');
	},

	set_warehouse(frm) {
		// Only allow individual warehouses if default warehouse is NOT set - otherwise sales order will override the changes.

		frm.fields_dict.items.grid.toggle_reqd('warehouse', !frm.doc.set_warehouse);
		frm.fields_dict.items.grid.toggle_enable('warehouse', !frm.doc.set_warehouse);

		frm.fields_dict.labour_travel.grid.toggle_reqd('warehouse', !frm.doc.set_warehouse);
		frm.fields_dict.labour_travel.grid.toggle_enable('warehouse', !frm.doc.set_warehouse);

		if (frm.doc.set_warehouse) {
			frm.doc.items?.forEach(item => item.warehouse = frm.doc.set_warehouse);
			frm.doc.labour_travel?.forEach(item => item.warehouse = frm.doc.set_warehouse);
		}

		frm.fields_dict.items.grid.refresh();
		frm.fields_dict.labour_travel.grid.refresh();
	}

});


frappe.ui.form.on('Service Report Item', {
	items_add: function (frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		if (!row.warehouse && frm.doc.set_warehouse) {
			frappe.model.set_value(cdt, cdn, "warehouse", frm.doc.set_warehouse);
		}
	}
});