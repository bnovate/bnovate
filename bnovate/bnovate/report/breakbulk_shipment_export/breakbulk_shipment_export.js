// Copyright (c) 2016, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Breakbulk Shipment Export"] = {
	filters: [
		{
			fieldname: "mawb",
			label: __("Breakbulk Master No"),
			fieldtype: "Select",
			options: [], // Initially empty, populated on load
		}, {
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1
		}
	],
	async onload(report) {
		this.report = report;

		// Populate Breakbulk Master No filter
		const mawbs = await bnovate.utils.get_mawbs();
		const options = [""].concat(mawbs);
		report.get_filter("mawb").df.options = options;
		report.get_filter("mawb").value = mawbs[0] || "";
		report.get_filter("mawb").refresh();
	},
};
