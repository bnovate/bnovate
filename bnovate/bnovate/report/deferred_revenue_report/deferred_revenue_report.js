// Copyright (c) 2016, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Deferred Revenue Report"] = {
    initial_depth: 2,
    filters: [
        {
            "fieldname": "account",
            "label": __("Account"),
            "fieldtype": "Link",
            "options": "Account"
        }, {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.month_end(),
            "reqd": 1,
        }
    ],
    onload(report) {
        this.report = report;
        this.colours = ["dark", "light"];
    },
    formatter(value, row, col, data, default_formatter) {
        // alternate colours of debits by posting date:

        if (col.colIndex == 0 || data.indent < 2) {
            return default_formatter(value, row, col, data)
        }
        return `<span class="coloured ${this.colours[data.date_rank % this.colours.length]}">${default_formatter(value, row, col, data)}</span>`;
    }
};
