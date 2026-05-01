// Copyright (c) 2016, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Revenue Analytics"] = {
	filters: [
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -12),
			"reqd": 1
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1
		},
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
	},
	formatter: function (value, row, col, data, default_formatter) {

		if (this.max_indent === null) {
			this.max_indent = Math.max(...frappe.query_report.data.map(d => d.indent || 0));
		}

		if (data.indent < this.max_indent) {
			return `<span class="coloured ${this.colours[data.indent % this.colours.length]}">${default_formatter(value, row, col, data)}</span>`;
		}

		return default_formatter(value, row, col, data);
	}
};
