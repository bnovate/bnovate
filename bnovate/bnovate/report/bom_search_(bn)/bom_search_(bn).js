// Copyright (c) 2016, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["BOM Search (bN)"] = {
	"filters": [
		{
			fieldname: "item1",
			label: __("Item 1"),
			fieldtype: "Link",
			options: "Item"
		},
		{
			fieldname: "only_active",
			label: __("Only Active BOMs"),
			fieldtype: "Check",
			default: 1
		},
		{
			fieldname: "only_default",
			label: __("Only Default BOMs"),
			fieldtype: "Check",
			default: 1
		},
		{
			fieldname: "only_active_items",
			label: __("Only Active Output Items"),
			fieldtype: "Check",
			default: 1
		},
		// {
		// 	fieldname: "search_sub_assemblies",
		// 	label: __("Search Sub Assemblies"),
		// 	fieldtype: "Check",
		// },
	]
};
