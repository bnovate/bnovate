// Copyright (c) 2023, bNovate, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.require([
    "/assets/frappe/js/lib/frappe-gantt/frappe-gantt.min.js",
    "/assets/frappe/js/lib/frappe-gantt/frappe-gantt.css",
])

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
            "options": "Subscription Service"
        },
    ],
    async onload(report) {
        await report.refresh();
        console.log(report)
        if (this.loaded === undefined) {
            report.$report.before('<div id="gantt">Gantt</div>');
            this.loaded = true;

            new Gantt("#gantt", build_gantt_data(report.data), {
                view_modes: ['Day', 'Week', 'Month', 'Quarter', 'Year'],
                view_mode: 'Quarter',
            });
        }
    },
    after_render() {
        console.log("after render")

    },
    refresh() {
        console.log("refresh");
    },
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

function build_gantt_data(report_data) {
    return report_data.map(row => ({
        id: `${row.subscription}-${row.sales_invoice}`,
        name: "Testing",
        start: row.service_start_date,
        end: row.service_end_date,
    }))
};