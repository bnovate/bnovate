// Copyright (c) 2016, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */
frappe.require("/assets/bnovate/js/modals.js")  // provides bnovate.modals

frappe.query_reports["Revenue Analytics"] = {
	filters: [
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": new Date(new Date().getFullYear(), 0, 1), // First day of calendar year.
			"reqd": 1
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": new Date(new Date().getFullYear(), 11, 31), // Last day of calendar year.
			"reqd": 1
		},
		{
			"fieldname": "include",
			"label": __("Include"),
			"fieldtype": "Select",
			"options": ["All", "Billed", "Unbilled"],
			"default": "All"
		},
		// {
		// 	"fieldname": "interval",
		// 	"label": __("Time Interval"),
		// 	"fieldtype": "Select",
		// 	"options": ["Month", "Quarter", "Year"],
		// 	"default": "Month"
		// },
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
			"reqd": 1
		},
	],
	tree: true,
	name_field: "revenue_stream_name",
	parent_field: "parent_revenue_stream",
	initial_depth: 2,
	onload: function (report) {
		this.report = report;
		this.colours = ["darker", "dark", "light"];
		this.max_indent = null;

		bnovate.modals.attach_report_modal("masterModal");
	},
	formatter: function (value, row, col, data, default_formatter) {

		if (this.max_indent === null) {
			this.max_indent = Math.max(...frappe.query_report.data.map(d => d.indent || 0));
		}

		if (data.indent < this.max_indent) {
			return `<span class="coloured ${this.colours[data.indent % this.colours.length]}">${default_formatter(value, row, col, data)}</span>`;
		} else {
			return this.build_master_link(default_formatter(value, row, col, data), data.revenue_stream_name, col.fieldname);
		}

		return default_formatter(value, row, col, data);
	},
	build_master_link(display_text, revenue_stream, month) {
		let from_date = frappe.query_report.filters?.find(f => f.fieldname === "from_date")?.get_value();
		let to_date = frappe.query_report.filters?.find(f => f.fieldname === "to_date")?.get_value();

		if (month !== 'total') {
			const m = moment(month, "YYYY-MM");
			from_date = m.startOf("month").format("YYYY-MM-DD");
			to_date = m.endOf("month").format("YYYY-MM-DD");
		};

		const filters = {
			revenue_stream,
			from_date,
			to_date,
			company: frappe.query_report.filters?.find(f => f.fieldname === "company")?.get_value() || frappe.defaults.get_user_default("Company"),
			include: frappe.query_report.filters?.find(f => f.fieldname === "include")?.get_value() || "All",
		};

		return bnovate.modals.report_link(
			display_text,
			"masterModal",
			"Revenue Analytics Master",
			`Revenue Analytics - ${revenue_stream} - ${month}`,
			filters
		)
	},
};
