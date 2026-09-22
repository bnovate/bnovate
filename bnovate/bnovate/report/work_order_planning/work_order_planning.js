// Copyright (c) 2023, bNovate, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.require("/assets/bnovate/js/lib/gcharts/loader.js")
frappe.require("/assets/bnovate/js/modals.js")  // provides bnovate.modals
frappe.require("/assets/bnovate/js/charts.js")  // provides bnovate.charts

frappe.query_reports["Work Order Planning"] = {
    filters: [
        {
            "fieldname": "workstation",
            "label": __("Workstation"),
            "fieldtype": "Link",
            "options": "Workstation"
        },
        {
            "fieldname": "simple_view",
            "label": __("Simple View"),
            "fieldtype": "Check",
        },
        {
            "fieldname": "show_chart",
            "label": __("Show Chart"),
            "fieldtype": "Check",
        },
    ],
    async onload(report) {
        this.report = report;
        this.colours = ["dark", "light"];

        // report.page.add_inner_button(__('Toggle Chart'), () => {
        //     if (this.report.$chart.is(':visible')) {
        //         this.report.$chart.hide();
        //     } else {
        //         this.report.$chart.show();
        //     }
        // })

        // save a click:
        let stations = await frappe.db.get_list("Workstation", { fields: ["name", "disabled"] });
        stations
            .filter(station => !station.disabled)
            .forEach(station => report.page.add_inner_button(station.name, () => {
                this.report.set_filter_value('workstation', station.name);
            }));

        bnovate.modals.attach_report_modal("stockModal");
        bnovate.modals.attach_report_modal("cartStatusModal");
    },
    after_datatable_render(datatable) {

        if (this.report.get_filter_value('show_chart')) {
            bnovate.charts.draw_timeline_chart(this.report, build_wo_dt);
            // this.report.$chart.hide();
        }

        // Activate tooltips on columns
        $(function () {
            $('[data-toggle="tooltip"]').tooltip()
        })

    },
    formatter(value, row, col, data, default_formatter) {
        let skip_default = false;
        let simple_view = this.report.get_filter_value('simple_view');

        if (col.fieldname === "sufficient_stock") {
            const color = ['red', 'orange', 'green'][value];
            return `<span class="indicator ${color}"></span>`;
        }
        if (data.indent === 1) {
            if (['planned_start_date', 'comment', 'status'].indexOf(col.fieldname) >= 0) {
                return '';
            } else if (col.fieldname === 'item_code') {
                return projected_stock_link(data.item_code, data.warehouse, data.item_name);
            }
        } else {
            if (col.fieldname === 'comment' && value) {
                value = `<span title="${value}">${value}</span>`
            } else if (col.fieldname === 'work_order') {
                if (simple_view) {
                    value = `<a href="/desk#work-order-execution?work_order=${value}">${value}</a>`;
                } else {
                    value = frappe.utils.get_form_link("Work Order", value, true);
                }
            } else if (col.fieldname === 'serial_no' && data.serial_no) {
                value = `${cartridge_status_link(data.serial_no)}`;
            } else if (col.fieldname === 'status') {
                let [legend, colour] = work_order_indicator(data);
                return `<span class="coloured ${this.colours[data.idx % this.colours.length]}">
                        <span class="indicator ${colour}">${legend}</span>
                    </span>
                    `;
            } else if (value && (col.fieldname === 'planned_start_date' || col.fieldname === 'expected_delivery_date')) {
                let date = value.substr(0, 10);
                if (simple_view) {
                    value = date
                } else {
                    value = `<a onclick="edit_date('${data.work_order}', '${data.planned_start_date}', '${data.expected_delivery_date || ''}')">${default_formatter(date, row, col, data)}</a>`;
                    skip_default = true;
                }
            } else if (col.fieldname === 'item_code') {
                value = projected_stock_link(data.item_code, data.warehouse, data.item_name);
                skip_default = true;
            } else if ((col.fieldname === 'time_estimate_remaining' || col.fieldname === 'mean_time_per_unit') && value) {
                // This will work as long as duration is less than 24h...
                let format_string = col.fieldname === 'time_estimate_remaining' ? 'HH:mm' : 'HH:mm.ss';
                value = moment.utc().startOf('day').add(value, 'minutes').format(format_string);
            }

            if (skip_default) {
                return `<span class="coloured ${this.colours[data.idx % this.colours.length]}">${value}</span>`;
            }
            return `<span class="coloured ${this.colours[data.idx % this.colours.length]}">${default_formatter(value, row, col, data)}</span>`;
        }
        return default_formatter(value, row, col, data)
    },
    initial_depth: 0,
};

// Stolen from work_order_list.js on ERPNext 
function work_order_indicator(doc) {
    if (doc.status === "Submitted") {
        return [__("Not Started"), "orange"];
    } else {
        return [__(doc.status), {
            "Draft": "red",
            "Stopped": "red",
            "Not Started": "red",
            "In Process": "orange",
            "Completed": "green",
            "Cancelled": "darkgrey"
        }[doc.status]];
    }
}

function cartridge_status_link(serial_nos) {
    return bnovate.modals.report_link(
        serial_nos,
        'cartStatusModal',
        'Cartridge Status',
        `Cartridge Status for this SO item`,
        {
            serial_no: serial_nos,  // Note that this is encoded in a data- tag, so it'll be a comma-separated string
        });
}

async function edit_date(work_order, start_date, delivery_date) {

    // start_date is a full datetime ("2025-05-01 08:50:23"); the dialog below
    // only lets the user pick a new date, so keep the original time-of-day
    // instead of letting it collapse to midnight.
    const original_time = (start_date && start_date.includes(" ")) ? start_date.split(" ")[1] : "08:00:00";

    const fields = [{
        fieldname: "new_start_date",
        fieldtype: "Date",
        label: __("New Start Date"),
        default: start_date,
    }, {
        fieldname: "new_delivery_date",
        fieldtype: "Date",
        label: __("New Delivery Date"),
        default: delivery_date,
    }];

    let values = await bnovate.utils.prompt("Edit dates", fields, "Confirm", "Cancel")

    if (!values) {
        return;
    }

    await frappe.db.set_value("Work Order", work_order, "planned_start_date", `${values.new_start_date} ${original_time}`);
    if (values.new_delivery_date) {
        await frappe.db.set_value("Work Order", work_order, "expected_delivery_date", values.new_delivery_date);
    }
    frappe.query_report.refresh();
}

function projected_stock_link(item_code, warehouse, item_name) {
    return bnovate.modals.report_link(
        `${item_code}${item_name ? ': ' + item_name : ''}`,
        'stockModal',
        'Projected Stock',
        `Projected stock for ${item_code} in ${warehouse}`,
        {
            item_code,
            warehouse,
        });
}

function build_wo_dt(report) {
    var dataTable = new google.visualization.DataTable();

    dataTable.addColumn({ type: 'string', id: 'Workstation' });
    dataTable.addColumn({ type: 'string', id: 'Work Order' });
    dataTable.addColumn({ type: 'string', id: 'tooltip', role: 'tooltip' });
    dataTable.addColumn({ type: 'string', id: 'style', role: 'style' });
    dataTable.addColumn({ type: 'date', id: 'Start' });
    dataTable.addColumn({ type: 'date', id: 'End' });

    const frappeColors = {
        red: "#ff5858",
        orange: "#ffb65c",
        green: "#98d85b",
    }

    let rows = report.data
        .filter(row => row.indent == 0)
        .map(row => [
            row.workstation || "Unknown",
            row.work_order,
            // "fill me later",
            frappe.render_template(`
                <div class="preview-popover-header">
                    <div class="preview-header">
                    </div>

                    <div class="preview-header">
                        <div class="preview-main">
                            <a class="preview-name bold" href="#Form/Work Order/{{ work_order }}">{{ work_order }}: {{ item_name }}</a>
                            <br>
                            <span class="small preview-value">
                                Item {{ projected_stock_link(item_code, warehouse) }}
                            </span>
                            <br>
                            <span class="small text-muted">{{ planned_start_date }} {% if planned_end_date %} - {{ planned_end_date }}{% endif %}</span>
                        </div>
                    </div>
                </div>
                <hr>
                <div class="popover-body">
                    <div class="preview-table" style="max-width: none;">
                        <div class="preview-field">
                            <div class="small preview-value text-muted">
                                <table class="table table-condensed no-margin" style="border-bottom: 1px solid #d1d8dd; width:100%">
                                <thead>
                                    <th class="text-center">Qty planned</th>
                                    <th class="text-center">produced</th>
                                    <th class="text-center">remaining</th>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td class="text-center">{{ planned_qty }}</td>
                                        <td class="text-center">{{ produced_qty }}</td>
                                        <td class="text-center">{{ required_qty }}</td>
                                    </tr>
                                </tbody>
                                </table>
                            </div>
                        </div>
                        <div class="preview-field">
                            <div class="small preview-value">
                                <table class="table table-condensed no-margin" style="border-bottom: 1px solid #d1d8dd; width:100%">
                                <thead>
                                    <th></th>
                                    <th class="text-left">Item</th>
                                    <th class="text-left">Name</th>
                                    <th class="text-right">Required</th>
                                    <th class="text-right">Proj. Stock</th>
                                    <th class="text-right">Guar. Stock</th>
                                </thead>
                                <tbody>
                                    {% for item in items %}
                                    <tr>
                                        <td><span class="indicator {{ ["red", "orange", "green"][item.sufficient_stock] }}"></span></td>
                                        <td class="text-left">
                                            {{ projected_stock_link(item.item_code, item.warehouse) }}
                                        </td>
                                        <td class="text-left">{{ frappe.ellipsis(item.item_name, 30) }}</td>
                                        <td class="text-right">{{ -item.qty }}</td>
                                        <td class="text-right">{{ item.projected_stock }}</td>
                                        <td class="text-right">{{ item.guaranteed_stock }}</td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            `, {
                ...row,
                items: report.data.filter(item => item.detail_doctype === "Work Order Item" && item.work_order === row.work_order)
            }),
            `color: ${frappeColors[row.stock_indicator]}`,
            frappe.datetime.str_to_obj(row.planned_start_date),
            frappe.datetime.str_to_obj(
                row.planned_end_date ||
                row.planned_start_date + " 12:00:00"
            ),
        ])
    dataTable.addRows(rows);
    return dataTable;
}