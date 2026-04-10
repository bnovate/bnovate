// Copyright (c) 2016-2026, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["All on Stock"] = {
	"filters": [
		{
			'fieldtype': 'Date',
			'fieldname': 'date',
			'label': __("Date"),
			'default': frappe.datetime.get_today(),
			'reqd': 1
		}
	]
};
