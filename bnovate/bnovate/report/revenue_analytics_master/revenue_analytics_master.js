// Copyright (c) 2016, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Revenue Analytics Master"] = {
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
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
			"reqd": 1
		},
		{
			fieldname: "revenue_streams",
			label: __("Revenue Streams"),
			fieldtype: "MultiSelectList",
			get_data: async function () {
				const revenue_streams = await frappe.db.get_list("Revenue Stream", {
					fields: ["name", "revenue_stream_name"],
					order_by: "lft",
					filters: {
						is_group: 0,
					}
				});
				return revenue_streams.map(rs => ({ value: rs.name, label: rs.revenue_stream_name }));
			},
			on_change: function () {
				frappe.query_report.refresh();
			},
		},

	],
	async onload(report) {
		// Select all revenue streams by default
		const stream_filter = frappe.query_report.get_filter("revenue_streams");
		if (stream_filter && !stream_filter.get_value()?.length) {
			const revenue_streams = await frappe.db.get_list("Revenue Stream", {
				fields: ["name"],
				order_by: "lft",
				filters: {
					is_group: 0,
				}
			});

			stream_filter.set_value(revenue_streams.map(rs => rs.name));
		}
	},
};
