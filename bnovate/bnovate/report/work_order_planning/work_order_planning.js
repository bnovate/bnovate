// Copyright (c) 2016, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.require("/assets/bnovate/js/lib/gcharts/loader.js")
frappe.require("/assets/bnovate/js/modals.js")  // provides bnovate.modals

frappe.query_reports["Work Order Planning"] = {
    filters: [
        {
            "fieldname": "workstation",
            "label": __("Workstation"),
            "fieldtype": "Link",
            "options": "Workstation"
        },
    ],
    onload(report) {
        this.report = report;
        this.colours = ["dark", "light"];

        report.page.add_inner_button(__('Toggle Chart'), () => {
            if (this.report.$chart.is(':visible')) {
                this.report.$chart.hide();
            } else {
                this.report.$chart.show();
            }
        })

        // bind_modal(report);
        bnovate.modals.attach_report_modal("reportModal");
    },
    after_datatable_render(datatable) {
        draw_google_chart(this.report);

        // Activate tooltips on columns
        $(function () {
            $('[data-toggle="tooltip"]').tooltip()
        })
    },
    formatter(value, row, col, data, default_formatter) {
        skip_default = false;
        if (col.fieldname === "sufficient_stock") {
            color = ['red', 'orange', 'green'][value];
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
            } else if (col.fieldname === 'status') {
                let [legend, colour] = work_order_indicator(data);
                return `<span class="coloured ${this.colours[data.idx % this.colours.length]}">
                        <span class="indicator ${colour}">${legend}</span>
                    </span>
                    `;
            } else if (col.fieldname === 'planned_start_date') {
                value = value.substr(0, 10);
            } else if (col.fieldname === 'item_code') {
                value = projected_stock_link(data.item_code, data.warehouse, data.item_name);
                skip_default = true;
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


function projected_stock_link(item_code, warehouse, item_name) {
    return bnovate.modals.report_link(
        `${item_code}${item_name ? ': ' + item_name : ''}`,
        'reportModal',
        'Projected Stock',
        `Projected stock for ${item_code} in ${warehouse}`,
        {
            item_code,
            warehouse,
        });
}

// Popover is the popup shown when clicking a bar on the timeline chart.
// #sacrificial is a little 0x0 px square created at the location clicked.
function dismiss_popover() {
    $('#sacrificial').popover('hide');
    $('#sacrificial').remove();
}

function draw_google_chart(report) {
    report.$chart.html(`
            <div class="chart-container">
                <div id="timeline" class="report-chart">Timeline</div>
            </div>
    `);

    // Track mouse position in chart to draw popover at correct location
    report.mousePos = { x: 0, y: 0 };
    let container = document.getElementById("timeline");
    container.addEventListener("mousemove", (e) => {
        report.mousePos.x = e.offsetX;
        report.mousePos.y = e.offsetY;
    });

    google.charts.load('current', { 'packages': ['timeline'] });
    google.charts.setOnLoadCallback(drawChart);
    function drawChart() {
        let chart = new google.visualization.Timeline(container);
        report.chart = chart;

        report.chart_dt = build_google_dt(report);

        // Show a popover when a timeline element is clicked. Popovers in bootstrap 3 don't
        // delete nicely, so I made a workaround where I create a sacrificial div centered on the
        // click and bind the popover to this div.
        google.visualization.events.addListener(chart, 'select', () => {

            dismiss_popover();

            $(container).append(
                `<div id="sacrificial" style="left: ${report.mousePos.x}px; top: ${report.mousePos.y}px"></div>`
            )

            let row = chart.getSelection()[0].row;
            let contents = report.chart_dt.getValue(row, 2);

            $("#sacrificial").popover({
                container: "body",
                title: "My fancy popover",
                html: true,
                content: contents,
                placement: "bottom",
            }).popover('show');

        });

        // Any click outside the popover dismisses it. May interfere with other popovers...
        document.addEventListener("click", (event) => {
            const popover = $(".popover");
            if (popover.is(event.target) || popover.has(event.target).length) {
                // Ignore if click target is inside a popover
                return;
            }
            dismiss_popover();
        });
        frappe.route.on('change', () => { dismiss_popover() });

        chart.draw(report.chart_dt, {
            height: 250,
            fontName: "Open Sans",
            tooltip: {
                // isHtml: true,
                trigger: 'both', // disable it

            },
        });
    }
}

function build_google_dt(report) {
    var dataTable = new google.visualization.DataTable();

    dataTable.addColumn({ type: 'string', id: 'Workstation' });
    dataTable.addColumn({ type: 'string', id: 'Work Order' });
    dataTable.addColumn({ type: 'string', id: 'tooltip', role: 'tooltip' });
    dataTable.addColumn({ type: 'string', id: 'style', role: 'style' });
    dataTable.addColumn({ type: 'date', id: 'Start' });
    dataTable.addColumn({ type: 'date', id: 'End' });

    frappeColors = {
        red: "#ff5858",
        orange: "#ffb65c",
        green: "#98d85b",
    }

    rows = report.data
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