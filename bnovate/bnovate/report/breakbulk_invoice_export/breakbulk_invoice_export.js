// Copyright (c) 2016, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Breakbulk Invoice Export"] = {
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

		report.page.add_inner_button(__('<i class="fa fa-download"></i> Export to CSV'), () => {
			const column_row = this.report.columns.map(col => col.label);
			const data = this.report.get_data_for_csv();
			const out = [column_row].concat(data);

			frappe.tools.downloadify(out, null, this.report.report_name);
		});

		report.page.add_inner_button(__('<i class="fa fa-download"></i> Commercial Invoices'), () => {
			const dn_list = Array.from(new Set(frappe.query_report.data.map(row => row.dn_name)));
			bnovate.utils.open_pdf_urls("Delivery Note", dn_list, "Commercial Invoice CHF");
		});

		report.page.add_inner_button(__('<i class="fa fa-calculator"></i> Sum Shipping'), () => {
			let shipping = frappe.query_report.data
				.filter(row => row.item_name === 'Shipping')
				.reduce((acc, row) => acc + row.base_declared_amount, 0);

			bnovate.utils.html_dialog('Total shipping charged',
				`Sum of shipping rows:<br><br> <b>${shipping.toFixed(2)}</b> CHF`);
		})
	},
};
