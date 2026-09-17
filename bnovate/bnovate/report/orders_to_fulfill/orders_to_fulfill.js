// Copyright (c) 2016, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */


frappe.require("/assets/bnovate/js/modals.js")  // provides bnovate.modals

frappe.query_reports["Orders to Fulfill"] = {
	filters: [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
			"reqd": 0
		},
		{
			"fieldname": "only_manufacturing",
			"label": __("Only manufactured items"),
			"fieldtype": "Check",
			"default": 0
		},
		{
			"fieldname": "include_drafts",
			"label": __("Include Drafts"),
			"fieldtype": "Check",
			"default": 0
		},
		{
			"fieldname": "sales_order",
			"label": __("Sales Order"),
			"fieldtype": "Link",
			"options": "Sales Order",
			"default": 0
		}
	],
	initial_depth: 0,
	onload(report) {
		this.report = report;
		this.week_index = 1;
		this.date_index = 1;
		this.colours = ["light", "dark"];


		report.page.add_inner_button(__('Toggle Chart'), () => {
			if (this.report.$chart.is(':visible')) {
				this.report.$chart.hide();
			} else {
				this.report.$chart.show();
			}
		})

		bnovate.modals.attach_report_modal("cartStatusModal");
	},
	after_datatable_render(datatable) {
		// Activate tooltips on columns
		$(function () {
			$('[data-toggle="tooltip"]').tooltip()
		});
		this.report.$chart.hide();
	},
	formatter(value, row, col, data, default_formatter) {
		if (col.fieldname === "sufficient_stock" && typeof value !== 'undefined') {
			let color = ['red', 'orange', 'yellow', 'green'][value];
			return `<span class="indicator ${color}"></span>`;
		}
		// Keep only a few columns for packed items.
		if (data.indent === 1 && ['remaining_qty', 'item_code', 'projected_stock', 'guaranteed_stock', 'work_order'].indexOf(col.fieldname) < 0) {
			return "";
		}
		if (col.fieldname === "work_order" && data.work_order) {
			if (data.work_order_acc) {
				return data.work_order_acc.map(r => {
					let [legend, colour] = work_order_indicator(r);
					return ` <span class="indicator ${colour}">${frappe.utils.get_form_link("Work Order", r.work_order, true)}</span> (${r.wo_produced_qty}/${r.wo_qty})`;
				}).join(", ");
			}
			let [legend, colour] = work_order_indicator(data);
			return ` <span class="indicator ${colour}">${frappe.utils.get_form_link("Work Order", value, true)}, ${legend}</span> (${data.wo_produced_qty}/${data.wo_qty})`;
		}
		if (col.fieldname === "serial_nos" && data.serial_nos) {
			return `${cartridge_status_link(data.serial_nos)}`;
		}
		if (col.fieldname === "weeknum") {
			return `<span class="coloured ${this.colours[data.week_index % this.colours.length]}">${default_formatter(value, row, col, data)}</span>`;
		}
		if (col.fieldname === "customer_name") {
			return `<span class="coloured ${this.colours[data.so_index % this.colours.length]}">${frappe.utils.get_form_link("Customer", data.customer, true, data.customer_name)}</span>`;
		}
		if (col.fieldname === "sales_order" || col.fieldname === "customer") {
			return `<span class="coloured ${this.colours[data.so_index % this.colours.length]}">${default_formatter(value, row, col, data)} ${breakbulk_indicator(data)} </span>`;
		}
		if (col.fieldname === "ship_date") {
			return `<span class="coloured ${this.colours[data.day_index % this.colours.length]}">${default_formatter(value, row, col, data)}</span>`;
		}
		if (col.fieldname === "open_delivery_notes") {
			if (value) {
				let [legend, colour] = delivery_note_indicator(data);
				return ` <span class="indicator ${colour}">${value.split(" ").map(n => frappe.utils.get_form_link("Delivery Note", n, true))}, ${legend}</span> (${data.open_delivery_qty}/${data.remaining_qty})`;
			} else {
				return `<button class="btn btn-xs btn-primary create-dn" onclick="create_grouped_dn('${data.sales_order}', '${data.customer}', '${data.ship_date}', '${data.shipping_address_name}')">Create DN</button>`;

			}
		}
		return default_formatter(value, row, col, data);
	}
};

// Stolen from work_order_list.js on ERPNext 
function work_order_indicator(doc) {
	if (doc.wo_status === "Submitted") {
		return [__("Not Started"), "orange"];
	} else {
		return [__(doc.wo_status), {
			"Draft": "red",
			"Stopped": "red",
			"Not Started": "red",
			"In Process": "orange",
			"Completed": "green",
			"Cancelled": "darkgrey"
		}[doc.wo_status]];
	}
}

function delivery_note_indicator(row) {
	// With the current SQL query, only draft DNs can appear...
	return ["Draft", "red"]
}

function breakbulk_indicator(row) {
	if (!row.breakbulk_master_no) {
		return "";
	}
	return ` <i class="fa fa-cubes text-muted" data-toggle="tooltip" data-placement="right" title="${__("Breakbulk")}: ${frappe.utils.escape_html(row.breakbulk_master_no)}"></i>`;
}

function cartridge_status_link(serial_nos) {
	return bnovate.modals.report_link(
		serial_nos,
		'cartStatusModal',
		'Cartridge Status',
		`Cartridge Status for this SO item`,
		{
			serial_no: serial_nos,  // Note that this is encoded in a data- tag, so it'll be a comma-separated string
		});
}

/*
	- Check if multiple orders were planned for same day, same customer, and same address.
	- If so, offer to group orders
	- In all cases, show serial numbers that need to be packed
	- Create draft DN and calculate appropriate shipping charge.
*/
async function create_grouped_dn(so_docname, customer, ship_date, shipping_address_name) {


	/* --------- OFFER GROUPING / SKIP IF IRRELEVANT --------------- */

	const group_potential = frappe.query_report.data
		.filter(row => (
			row.customer == customer &&
			row.ship_date == ship_date &&
			row.shipping_address_name == shipping_address_name &&
			row.indent == 0 &&
			row.open_delivery_notes == null
		));

	let so_docnames = new Set(group_potential.map(row => row.sales_order));

	let group_orders = false;
	if (so_docnames.size > 1) {
		// Orders could be grouped
		const msg_body = frappe.render_template(`
			<p>Multiple sales orders can be shipped to the same address that day</p>
			<table class="table table-condensed no-margin" style="border-bottom: 1px solid #d1d8dd">
				<thead>
				 	<th>SO</th>
					<th>Qty</th>
					<th>Item Name</th>
				</thead>
				<tbody>
					{% for row in rows %}
					<tr>
						<td>{{ row.sales_order }}</td>
						<td>{{ row.remaining_qty }}</td>
						<td><b>{{ row.item_name }}</b></td>
					</tr>
					{% endfor %}
				</tbody>
			</table>
		`, { rows: group_potential });

		const do_group = await bnovate.utils.prompt(
			`Group orders?`,
			[{
				fieldname: 'description',
				fieldtype: 'HTML',
				options: msg_body,
			}],
			"Group Orders",
			"Don't Group"
		);

		if (do_group) {
			group_orders = true;
		}
	}


	let retained_rows = group_potential;
	if (!group_orders) {
		retained_rows = group_potential.filter(row => row.sales_order == so_docname);
		so_docnames = [];
	}

	/* --------- DISPLAY ITEMS TO PREPARE --------------- */

	const item_detail_docnames = retained_rows.map(row => row.detail_docname);
	const display_rows = retained_rows
		.filter(row => row.serial_nos)
		.map(row => ({
			...row,
			serial_nos: row.serial_nos?.trim().split('\n') || []
		}))

	const msg_body = frappe.render_template(`
		<table class="table table-condensed no-margin" style="border-bottom: 1px solid #d1d8dd">
			<thead>
				<th>SO</th>
				<th>Qty</th>
				<th>Item Name</th>
			</thead>
			<tbody>
				{% for row in rows %}
				<tr>
					<td>{{ row.sales_order }}</td>
					<td>{{ row.remaining_qty }}</td>
					<td><b>{{ row.item_name }}</b>
						<ul>
						{% for sn in row.serial_nos %}
							<li>{{ sn }}</li>
						{% endfor %}
						</ul>
					</td>
				</tr>
				{% endfor %}
			</tbody>
		</table>
	`, { rows: display_rows });

	const ok = await bnovate.utils.prompt(
		`Prepare Serial Numbers:`,
		[{
			fieldname: 'description',
			fieldtype: 'HTML',
			options: msg_body,
		}],
		"Create DN",
		"Cancel"
	);

	if (!ok) {
		return;
	}


	/* --------- CREATE AGGREGATE DN --------------- */

	return frappe.model.open_mapped_doc({
		method: "bnovate.bnovate.report.orders_to_fulfill.orders_to_fulfill.create_grouped_dn",
		frm: {
			doc: {
				name: so_docname,
			},
			get_selected() {
				return []
			}
		},
		args: {
			so_docnames: Array.from(so_docnames),
			item_detail_docnames,
			ship_date,
			shipping_address_name,
		}
	});

};
