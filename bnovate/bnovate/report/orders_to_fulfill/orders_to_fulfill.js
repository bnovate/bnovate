// Copyright (c) 2016, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Orders to Fulfill"] = {
	filters: [
		{
			"fieldname": "only_manufacturing",
			"label": __("Only manufactured items"),
			"fieldtype": "Check",
			"default": 1
		},
		{
			"fieldname": "include_drafts",
			"label": __("Include Drafts"),
			"fieldtype": "Check",
			"default": 0
		}
	],
	initial_depth: 0,
	onload(report) {
		this.report = report;
		this.week_index = 1;
		this.date_index = 1;
		this.colours = ["light", "dark"];
	},
	formatter(value, row, col, data, default_formatter) {
		if (col.fieldname === "weeknum") {
			if (data.indent === 1) {
				return ""
			}
			return `<span class="coloured ${this.colours[data.week_index % this.colours.length]}">${default_formatter(value, row, col, data)}</span>`
		}
		if (col.fieldname === "ship_date") {
			if (data.indent === 1) {
				return ""
			}
			return `<span class="coloured ${this.colours[data.day_index % this.colours.length]}">${default_formatter(value, row, col, data)}</span>`
		}
		return default_formatter(value, row, col, data);
	}
};
