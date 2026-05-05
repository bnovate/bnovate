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
	],

};
