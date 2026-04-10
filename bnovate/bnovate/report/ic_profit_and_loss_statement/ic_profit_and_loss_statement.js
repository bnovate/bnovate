// Copyright (c) 2024, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["IC Profit And Loss Statement"] = {
    "filters": [
        {
            "fieldname":"from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": new Date((new Date()).getFullYear(), 0, 1),
            "reqd": 1
        },
        {
            "fieldname":"to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": new Date((new Date()).getFullYear(), 11, 31),
            "reqd": 1
        },
        {
            "fieldname":"eur_exchange_rate",
            "label": __("EUR Exchange Rate"),
            "fieldtype": "Float",
            "default": 1,
            "reqd": 1
        },
        {
            "fieldname":"gbp_exchange_rate",
            "label": __("GBP Exchange Rate"),
            "fieldtype": "Float",
            "default": 1,
            "reqd": 1
        }
    ],
    "onload": (report) => {
        frappe.db.get_value(
            "Currency Exchange", 
            filters={'from_currency': 'GBP', 'to_currency': 'CHF'}, 
            fields=['exchange_rate']
        ).then( function (response) {
            frappe.query_report.get_filter('gbp_exchange_rate').set_value(response.message.exchange_rate);
        });
        frappe.db.get_value(
            "Currency Exchange", 
            filters={'from_currency': 'EUR', 'to_currency': 'CHF'}, 
            fields=['exchange_rate']
        ).then( function (response) {
            frappe.query_report.get_filter('eur_exchange_rate').set_value(response.message.exchange_rate);
        });
    }
};
