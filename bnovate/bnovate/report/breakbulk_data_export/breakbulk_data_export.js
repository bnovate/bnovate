// Copyright (c) 2016, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Breakbulk Data Export"] = {
	filters: [
		{
			"fieldname": "date",
			"label": __("Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1
		}

	],
	onload(report) {
		this.report = report;
		report.page.add_inner_button(__('Export to CSV'), () => {
			const column_row = this.report.columns.map(col => col.label);
			const data = this.report.get_data_for_csv();
			const out = [column_row].concat(data);

			frappe.tools.downloadify(out, null, this.report.report_name);
		});
	},
};
