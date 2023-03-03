// Copyright (c) 2023, bNovate, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Subscription Invoices"] = {
    filters: [
        {
            "fieldname": "customer",
            "label": __("Customer"),
            "fieldtype": "Link",
            "options": "Customer"
        },
        {
            "fieldname": "subscription",
            "label": __("Subscription"),
            "fieldtype": "Link",
            "options": "Subscription Contract"
        },
    ],
    formatter(value, row, col, data, default_formatter) {
        // Copied from SINV's listview get_indicator
        var status_color = {
            "Draft": "grey",
            "Unpaid": "orange",
            "Paid": "green",
            "Return": "darkgrey",
            "Credit Note Issued": "darkgrey",
            "Unpaid and Discounted": "orange",
            "Overdue and Discounted": "red",
            "Overdue": "red",
            "Cancelled": "red"
        };
        if (col.fieldname === "status") {
            let color = status_color[value] ? status_color[value] : "grey";
            return `<span class="indicator ${color}">${value}</span>`
        }
        return default_formatter(value, row, col, data);
    }

};
