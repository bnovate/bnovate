// Copyright (c) 2023, bNovate, ITST, libracore and contributors
// For license information, please see license.txt

{% include 'erpnext/selling/sales_common.js' %}

frappe.provide('bnovate.subscription_contract');

frappe.ui.form.on('Subscription Contract', {
	async before_cancel(frm) {
		// Only allow cancellation if no invoices are open
		// Cancelling is blocked by the backend anyway, but I want a more helpful message for users.
		const invoices = await frappe.db.get_list("Sales Invoice", { filters: { subscription: frm.doc.name } });
		if (!invoices.length) {
			return;
		}
		await new Promise((resolve, reject) => {
			frappe.confirm("If invoices are already created, do not cancel. Change the subscription End Date instead.<br><br>Do you still want to try?",
				() => { resolve(); },
				() => {
					frappe.validated = false;
					resolve();
				}
			)
		});
	},

});

frappe.ui.form.on('Subscription Contract Item', {
	async price_list_rate(frm, cdt, cdn) {
		if (frm.doc.ignore_default_discount) {
			return;
		}

		await frappe.model.set_value(cdt, cdn, "discount_percentage", frm.doc.default_discount);
	},
});

// Subclass SellingController to use their price rate mechanisms
bnovate.subscription_contract.SubscriptionContractController = erpnext.selling.SellingController.extend({
	onload(doc, dt, dn) {
		this._super();

		this.frm.set_query('contact_person', function () {
			return {
				// contact_query from frappe package is more flexible than the one from erpnext
				query: 'frappe.contacts.doctype.contact.contact.contact_query',
				filters: {
					link_doctype: 'Customer',
					link_name: doc.customer,
				}
			}
		});
		// Override item filters set by SellingController
		this.frm.set_query("item_code", "items", function () {
			return { filters: { bn_requires_deferral: true } }
		});

		if (!this.frm.doc.start_date) {
			this.frm.set_value('start_date', frappe.datetime.add_days(frappe.datetime.month_end(), 1));
		}
	},
	refresh() {
		this.frm.doc.transaction_date = this.frm.doc.start_date; // Helps SellingController methods work for pricing for example
		if (this.frm.doc.docstatus == 1 && (this.frm.doc.stopped || this.frm.doc.tentative_end_date)) {
			render_checklist(this.frm);
		}

		if (this.frm.doc.docstatus == 1) {
			if (!this.frm.doc.stopped && this.frm.has_perm(WRITE)) {
				const label = __('Modify / Upgrade');
				this.frm.add_custom_button(label, async () => {
					try {
						this.frm.doc.tentative_end_date = await prompt_end_date();
					} catch {
						this.frm.reload_doc();
						return;
					}
					render_checklist(this.frm);
					this.frm.remove_custom_button(label);
				})
			}

			this.frm.add_custom_button(__("Create Invoice"), async () => {
				this.frm.trigger('create_invoices');
			});
		}
	},
	async customer(doc, dt, dn) {
		this._super();
		// Get default discount

		const resp = await frappe.db.get_value("Customer", { name: this.frm.doc.customer }, "default_discount")
		const default_discount = resp.message.default_discount || 0;
		this.frm.set_value("default_discount", default_discount);

		bnovate.utils.set_item_discounts(this.frm);

	},
	apply_default_discount() {
		bnovate.utils.set_item_discounts(this.frm);
	},
	start_date() {
		this.frm.doc.transaction_date = this.frm.doc.start_date; // Helps SellingController methods work for pricing for example
		this.frm.trigger('currency');
		this.frm.trigger('end_date');
		this.frm.trigger('planned_end_date');
	},
	interval() {
		this.frm.trigger('end_date');
		this.frm.trigger('planned_end_date');
	},
	planned_end_date() {
		console.log("trigged")
		if (this.frm.doc.planned_end_date) {
			const billing_end = this._get_next_billing_end(this.frm.doc.planned_end_date || frappe.datetime.get_today());
			if (billing_end != this.frm.doc.planned_end_date) {
				frappe.msgprint({
					title: __("Info"),
					message: __("Planned End Date was changed to the next end of billing cycle"),
					color: "green",
				});
				// Change value without re-triggering change watcher
				this.frm.doc.planned_end_date = billing_end;
				this.frm.refresh_field('planned_end_date');
			}
		}
	},
	end_date() {
		// Note: to force an end date in the middle of a billing period, use the "end_contract" workflow.
		// if end date is defined, set it to the end of a period.
		if (this.frm.doc.end_date) {
			const billing_end = this._get_next_billing_end(this.frm.doc.end_date);
			if (billing_end != this.frm.doc.end_date) {
				frappe.msgprint({
					title: __("Info"),
					message: __("End Date was changed to the next end of billing cycle"),
					color: "green",
				});
				this.frm.doc.end_date = billing_end;
				this.frm.refresh_field('end_date');
			}
		}
	},
	renewal_reminder_friendly(e) {
		// Set reminder in weeks based on user friendly values
		const lookup = {
			'': [null, 'WEEK'],
			'1 week': ['1', 'WEEK'],
			'2 weeks': ['2', 'WEEK'],
			'3 weeks': ['3', 'WEEK'],
			'1 month': ['1', 'MONTH'],
			'2 months': ['2', 'MONTH'],
			'3 months': ['3', 'MONTH'],
			'4 months': ['4', 'MONTH'],
		}

		let [count, period] = lookup[e.renewal_reminder_friendly];
		this.frm.set_value("renewal_reminder", count);
		this.frm.set_value("renewal_reminder_period", period);
	},
	tc_name() {
		this.get_terms();
	},


	_get_next_billing_end(current_end_date) {
		const interval = this.frm.doc.interval === "Yearly" ? 12 : 1;
		let billing_start = this.frm.doc.start_date;  // start of next billing period
		let billing_end = frappe.datetime.add_days(billing_start, -1) // end of previous billing period
		while (billing_start <= this.frm.doc.start_date || billing_end < current_end_date) {
			billing_start = frappe.datetime.add_months(billing_start, interval);
			billing_end = frappe.datetime.add_days(billing_start, -1)
		}
		return billing_end;
	},
	async create_invoices() {
		frappe.route_options = {
			"customer": this.frm.doc.customer,
		};
		await frappe.set_route("query-report", "Aggregate Invoicing");
		frappe.query_report.refresh();
	},

	// Modification workflow
	// - Confirm end date of current SC
	// - Ensure billing is created up to end_date
	// - Set status to Stopped
	// - If applicable, find last invoice(s) and adjust service end date
	// - If applicable, issue corresponding credit note(s)
	// - Duplicate SC, starting from day after end date.
	//   - Show on print format that it replaces previous SC.
	async check_invoice_status() {
		const resp = await frappe.call({
			method: 'bnovate.bnovate.report.aggregate_invoicing.aggregate_invoicing.check_invoice_status',
			args: {
				docname: this.frm.doc.name,
				end_date: this.frm.doc.tentative_end_date || this.frm.doc.end_date,
			},
		});
		return resp.message;
	},
	async confirm_end_date() {
		let end_date = await prompt_end_date(this.frm.doc.tentative_end_date);
		try {
			await this.end_contract(end_date);
		} finally {
			this.frm.reload_doc();
		}
	},
	async end_contract(end_date) {
		const resp = await frappe.call({
			method: 'bnovate.bnovate.doctype.subscription_contract.subscription_contract.end_contract',
			args: {
				docname: this.frm.doc.name,
				end_date: end_date,
			},
		})
		return resp.message;
	},
	async stop_invoices() {
		const resp = await frappe.call({
			method: 'bnovate.bnovate.doctype.subscription_contract.subscription_contract.stop_invoices',
			args: {
				docname: this.frm.doc.name,
			}
		})
		this.frm.reload_doc();
		return resp.message; // list of reimbursable SINV items
	},
	async create_credit_notes(sinv_items, selected_items) {
		const resp = await frappe.call({
			method: 'bnovate.bnovate.doctype.subscription_contract.subscription_contract.create_credit_notes',
			args: {
				docname: this.frm.doc.name,
				sinv_items,
				selected_items,
			}
		})
		this.frm.reload_doc();
		return resp.message
	},
	// Set stop date on invoices, calculated reimbursable amounts, create credit notes if user choses to.
	async adjust_billing() {
		let reimbursable_sinv_items = await this.stop_invoices();
		let selected = await prompt_credit_note_choice(reimbursable_sinv_items);
		console.log(selected);
		let credit_notes = await this.create_credit_notes(reimbursable_sinv_items, selected);
		if (credit_notes.length > 0) {
			frappe.msgprint(`Created credit note(s): ${credit_notes.map(cn => frappe.utils.get_form_link("Sales Invoice", cn.name, true, cn.name))}`);
		}
	},
	// Create a copy of current doc, but starting from day after end date.
	amend_stopped() {
		frappe.model.open_mapped_doc({
			method: 'bnovate.bnovate.doctype.subscription_contract.subscription_contract.make_from_self',
			frm: this.frm
		});
	},

	// override some methods from transaction.js

	_get_args(item) {
		let answer = this._super();
		answer.transaction_date = this.frm.doc.start_date;
		return answer
	},
	payment_terms_template() {
		// Do nothing, just override parent class behaviour of rebuilding terms table.
	},
	currency() {
		var transaction_date = this.frm.doc.start_date;
		var me = this;
		this.set_dynamic_labels();
		var company_currency = this.get_company_currency();
		// Added `ignore_pricing_rule` to determine if document is loading after mapping from another doc
		if (this.frm.doc.currency && this.frm.doc.currency !== company_currency
			&& !this.frm.doc.ignore_pricing_rule) {

			this.get_exchange_rate(transaction_date, this.frm.doc.currency, company_currency,
				function (exchange_rate) {
					if (exchange_rate != me.frm.doc.conversion_rate) {
						// me.set_margin_amount_based_on_currency(exchange_rate);
						// me.set_actual_charges_based_on_currency(exchange_rate);
						me.frm.set_value("conversion_rate", exchange_rate);
					}
				});
		} else {
			this.conversion_rate();
		}
	},
	get_exchange_rate(transaction_date, from_currency, to_currency, callback) {
		var args = "for_selling";

		if (!transaction_date || !from_currency || !to_currency) return;
		return frappe.call({
			method: "erpnext.setup.utils.get_exchange_rate",
			args: {
				transaction_date: transaction_date,
				from_currency: from_currency,
				to_currency: to_currency,
				args: args
			},
			callback: function (r) {
				callback(flt(r.message));
			}
		});
	},
})

$.extend(cur_frm.cscript, new bnovate.subscription_contract.SubscriptionContractController({ frm: cur_frm }));


/***************************
 * HELPERS
 ***************************/

function prompt_end_date(default_date) {
	return new Promise((resolve, reject) => {
		let d = new frappe.ui.Dialog({
			title: "Confirm end date of current Subscription",
			fields: [{
				label: "Actual End Date",
				fieldname: "end_date",
				fieldtype: "Date",
				default: default_date,
				reqd: 1
			}],
			primary_action_label: 'End Contract',
			primary_action(values) {
				resolve(values.end_date);
				d.hide();
			},
			secondary_action() {
				reject();
			}
		});
		d.show();
	})
}

function prompt_credit_note_choice(refundable_items) {
	const template = `
	{% if refundable_items.length == 0 %}
	<p>No credit notes needed, skip to next step.</p>

	{% else %}
		<table class="table">
		<tbody>
		<tr>
		 	<th></th>
			<th>SINV</th>
			<th>Period Start</th>
			<th>Net Amount</th>
			<th>Refundable Amount</th>
		</tr>
		{% for item in refundable_items %}
		<tr>
			<td><input type="checkbox" class="cn-select" data-name="{{ item.name }}" checked></td>
			<td><a href="{{ frappe.utils.get_form_link('Sales Invoice', item.sinv_name) }}" target="_blank">{{ item.sinv_name }}</a></td>
			<td>{{ frappe.format(item.service_start_date, { fieldtype: 'Date' }) }} </td>
			<td>{{ format_currency(item.net_amount, item.currency) }} </td>
			<td>{{ format_currency(item.refund, item.currency) }} </td>
		</tr>
		{% endfor %}
		</tbody>
		</table>
	{% endif %}
	`
	return new Promise((resolve, reject) => {
		let d = new frappe.ui.Dialog({
			title: "Chose invoices for credit note",
			fields: [{
				label: "Table",
				fieldname: "table",
				fieldtype: "HTML",
				options: frappe.render_template(template, { refundable_items })
			}],
			primary_action_label: refundable_items.length > 0 ? 'Create Credit Notes' : 'Next',
			primary_action(values) {
				const selected = [...document.querySelectorAll('.cn-select')]
					.filter(el => el.checked)
					.map(el => el.dataset.name);
				resolve(selected);
				d.hide();
			},
			secondary_action() {
				reject();
			}
		});
		d.show();
	})
}

async function render_checklist(frm) {

	// Empty element if it already existed

	const div = document.querySelector('#checklist') || document.createElement('div');
	div.innerHTML = '';

	div.setAttribute('class', 'row form-section');
	div.setAttribute('id', 'checklist');
	document.querySelector('.form-page').prepend(div);

	const template = `
	<div class="col-sm-12">
		<p>Complete the following steps to terminate this contract:</p>

		<ul>
			<li class="{% if invoices_done %}done{% endif %}">
				Create all invoices until end date
				{% if !invoices_done %}
				<button id="create-invoices" class="btn btn-primary btn-xs">Create Invoices</button>
				{% endif %}
			</li>
			<li class="{% if doc.stopped %}done{% endif %}">
				Set End Date
				{% if invoices_done && !doc.stopped %}
				<button id="end-contract" class="btn btn-primary btn-xs">Set End Date</button>
				{% endif %}
			</li>
			<li class="{% if doc.credit_confirmed %}done{% endif %}">
				Update Invoices and create Credit Notes if needed 
				{% if doc.stopped && !doc.credit_confirmed %}
				<button id="adjust-billing" class="btn btn-primary btn-xs">Adjust Billing</button>
				{% endif %}
			</li>
			<li class="{% if amended_links %}done{% endif %}">
				Create new subscription 
				{% if doc.credit_confirmed %}
					{% if !amended_links %}
						<button id="amend" class="btn btn-primary btn-xs">Amend</button>
					{% else %}
					: {{ amended_links }}
					{% endif %}
				{% endif %}
			</li>
		</ul>
	</div>
	`

	const invoiceable_entries = await frm.trigger('check_invoice_status');
	const invoices_done = invoiceable_entries.length == 0;

	const amended = await frappe.db.get_list("Subscription Contract", { filters: { amended_from: frm.doc.name } })
	const amended_links = amended
		.map(doc => frappe.utils.get_form_link("Subscription Contract", doc.name, true, doc.name))
		.join(", ");

	div.innerHTML = frappe.render_template(template, { doc: frm.doc, invoices_done, amended_links })

	document.querySelector('#create-invoices')?.addEventListener('click', () => {
		frm.trigger('create_invoices');
	})

	document.querySelector('#end-contract')?.addEventListener('click', () => {
		frm.trigger('confirm_end_date');
	})

	document.querySelector('#adjust-billing')?.addEventListener('click', () => {
		frm.trigger('adjust_billing');
	})

	document.querySelector('#amend')?.addEventListener('click', () => {
		frm.trigger('amend_stopped');
	})
}
