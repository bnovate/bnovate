/* Customisations for Delivery Note
 * 
 * Included by hooks.py to add client-side code
 * (same effect as writing a custom script)
 * 
 * - Removes legacy Create Subscription action
 * - Handles 'packing_stage' field: show when a DN is ready for pickup to be arranged.
 * 
 * 
 *  Workflow: 
 *      - Document is submitted when package is ready to leave, so as to validate and update stock.
 *      - 'Packing stage' changes to 'Ready to Ship'
 *      - Once shipped, stage changes to 'Shipped' and tracking info is updated.
 */

frappe.ui.form.on("Delivery Note", {

    before_load(frm) {
        frm.override_action_buttons = () => override_action_buttons(frm);
        frm.assign = () => assign(frm);

        frm.override_action_buttons();

        frm.dashboard.add_transactions({
            'items': ['Shipment'],
            'label': 'Related',
        });
    },

    onload(frm) {
        frm.set_query("custom_shipping_rule", () => {
            return {
                filters: {
                    country: frm.doc.shipping_country,
                }
            }
        })
    },

    refresh(frm) {

        if (frm.doc.shipping_label) {
            frm.add_custom_button(__('<i class="fa fa-print"></i> Shipping Label'), () => {
                print_shipping_label(frm);
            });
        }

        setTimeout(() => {
            frm.remove_custom_button(__("Subscription"), __("Create"));
            frm.add_custom_button(__("Aggregate Invoice"), async function () {
                frappe.route_options = {
                    "customer": frm.doc.customer,
                    "doctype": "Delivery Note",
                };
                await frappe.set_route("query-report", "Aggregate Invoicing");
                frappe.query_report.refresh();
            }, __("Create"));

            // Override standard delivery creation
            frm.remove_custom_button(__("Shipment"), __("Create"));
            frm.add_custom_button(__("Shipment"), () => create_shipment(frm), __("Create"));

            // Backup location for this function
            if (frm.doc.packing_stage != "Shipped") {
                frm.add_custom_button(__('Request DHL Pickup <i class="fa fa-truck"></i>'), () => {
                    request_pickup(frm);
                }, __("Create"));
            }


        }, 500);

        frm.override_action_buttons()
    },

    add_template(frm) {
        if (frm.doc.parcel_template) {
            frappe.model.with_doc("Shipment Parcel Template", frm.doc.parcel_template, () => {
                let parcel_template = frappe.model.get_doc("Shipment Parcel Template", frm.doc.parcel_template);
                let row = frappe.model.add_child(frm.doc, "Shipment Parcel", "shipment_parcel");
                row.length = parcel_template.length;
                row.width = parcel_template.width;
                row.height = parcel_template.height;
                row.weight = parcel_template.weight;
                frm.refresh_fields("shipment_parcel");
            });
        }
    },

    custom_shipping_rule(frm) {

        // Call Custom Shipping Rule instead of built-in one:
        if (frm.doc.custom_shipping_rule) {
            return frappe.call({
                method: 'bnovate.bnovate.doctype.custom_shipping_rule.custom_shipping_rule.apply_rule',
                args: {
                    doc: frm.doc,
                },
                callback: (r) => {
                    if (!r.exc) {
                        frm.refresh_fields();
                        frm.cscript.calculate_taxes_and_totals();
                    }
                },
                error: () => frm.set_value('custom_shipping_rule', ''),
            })
        }
        else {
            frm.cscript.calculate_taxes_and_totals();
        }

    },
})

// Return next weekday date, starting 'days_from_now' from today
// Setting days_from_now to 0 will return today if today is a weekday
function next_weekday(days_from_now = 0) {
    let d = frappe.datetime.add_days(frappe.datetime.now_date(), days_from_now);

    while (moment(d).isoWeekday() > 5) {
        d = frappe.datetime.add_days(d, 1)
    }
    return d;
}

async function prompt_shipment(frm) {

    // Pre-fill with next available pickup date
    const cutoff_time = await bnovate.utils.get_setting('same_day_cutoff');
    let pickup_date = frm.doc.posting_date;
    if (pickup_date <= frappe.datetime.now_date()) {
        if (frappe.datetime.now_time() < cutoff_time) {
            pickup_date = next_weekday(0);
        } else {
            pickup_date = next_weekday(1);
        }
    }

    const data = await bnovate.utils.prompt(
        __("Confirm Pickup Date"),
        [{
            label: __("Pickup Date"),
            fieldname: "pickup_date",
            fieldtype: "Date",
            reqd: 1,
            default: pickup_date,
        }],
        "Send to DHL",
        "Cancel",
    )
    return data;
}

async function create_shipment(frm) {
    const args = await prompt_shipment(frm);

    if (args === null) {
        console.log("Cancelled");
        return
    }

    frappe.model.open_mapped_doc({
        method: "bnovate.bnovate.utils.shipping.make_shipment_from_dn",
        frm,
        args,
    })
}

// Creates shipment, get shipping label from carrier, and request actual pickup!
async function request_pickup(frm) {
    const args = await prompt_shipment(frm);

    if (args === null) {
        console.log("Cancelled");
        return
    }

    const resp = await bnovate.realtime.call({
        method: "bnovate.bnovate.utils.shipping.ship_from_dn",
        args: {
            dn_docname: frm.doc.name,
            ...args,
        },
        callback(status) {
            console.log(status);
            if (status.data.progress < 100) {
                frappe.show_progress(__("Creating shipment..."), status.data.progress, 100, __(status.data.message));
            }
            if (status.code == 0) {
                frappe.hide_progress();
            }
        }
    })

    console.log(resp.message);
    await frm.reload_doc();
    await print_shipping_label(frm);
}

async function print_shipping_label(frm) {
    await bnovate.utils.print_url(frm.doc.shipping_label);
}

function override_action_buttons(frm) {

    if (frm.is_dirty()) {
        return;
    }

    if (frm.doc.docstatus === 1) {
        // Only override action button if form is submitted
        frm.page.clear_primary_action();
        if (frm.doc.packing_stage == "Packing") {

            // // We organize shipping if incoterm is DAP or DDP
            // if (frm.doc.incoterm == "DAP" || frm.doc.incoterm == "DDP") {
            //     frm.dashboard.add_comment(__("We organize shipping for this order") + ` (Incoterm ${frm.doc.incoterm})`);

            //     frm.page.set_primary_action(__("Ship with DHL") + ' <i class="fa fa-truck"></i>', async () => {
            //         return await request_pickup(frm);
            //     })

            // } else {
            // frm.dashboard.add_comment(__("The customer will organize shipping") + ` (Incoterm ${frm.doc.incoterm})`);
            frm.page.set_primary_action(__("Request Pickup") + ' <i class="fa fa-paper-plane"></i>', async () => {
                await frm.set_value({ packing_stage: 'Ready to Ship' });
                frm.save("Update");
                await frm.assign();
            })
            // }

        } else if (frm.doc.packing_stage == "Ready to Ship") {
            frm.page.set_primary_action(__("Confirm Shipment"), async () => {
                const values = await bnovate.utils.prompt("Enter shipping details",
                    [{
                        label: "Carrier",
                        fieldname: "carrier",
                        fieldtype: "Data",
                        reqd: 0,
                        default: frm.doc.carrier || "DHL",
                    }, {
                        label: "Tracking No",
                        fieldname: "tracking_no",
                        fieldtype: "Data",
                        reqd: 0,
                        default: frm.doc.tracking_no,
                    }],
                    "Confirm",
                    "Cancel"
                )
                frm.doc.packing_stage = 'Shipped';
                frm.doc.carrier = values.carrier;
                frm.doc.tracking_no = values.tracking_no;
                frm.save("Update");
                bnovate.utils.email_dialog(frm, await bnovate.utils.get_setting('dn_template'));
            })
        }
    }
};

async function assign(frm) {
    if (frm.is_new()) {
        frappe.throw(__("Please save the document before assignment"));
        return;
    }

    return new Promise((resolve, reject) => {
        const assign_to = new frappe.ui.form.AssignToDialog({
            obj: frm,
            method: 'frappe.desk.form.assign_to.add',
            doctype: frm.doctype,
            docname: frm.docname,
            callback: function (r) {
                resolve();
                me.render(r.message);
            }
        });
        // me.assign_to.dialog.clear();

        if (frm.meta.title_field) {
            assign_to.dialog.set_value("description", me.frm.doc[me.frm.meta.title_field])
        }

        assign_to.dialog.show();
    });
}