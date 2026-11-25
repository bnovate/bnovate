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
                    company: frm.doc.company,
                }
            }
        })

        frm.set_query('parcel_template', (doc) => {
            return {
                query: 'bnovate.bnovate.utils.shipping.parcel_query',
            }
        })
    },

    refresh(frm) {
        bnovate.utils.add_email_icon(frm, custom_mail_dialog);

        // const pdf_url = bnovate.utils.get_pdf_url(frm.doc.doctype, frm.doc.name, "Commercial Invoice CHF", frm.doc.language);
        // frm.add_custom_button(`<a href="${pdf_url}" download="${frm.doc.name}_invoice_CHF.pdf"><i class="fa fa-download"></i> Details</a> `, () => {
        //     frappe.show_progress("Preparing...", 50, 100);
        //     setTimeout(() => frappe.hide_progress(), 1000);
        // });

        if (frm.doc.shipping_label) {
            frm.add_custom_button('<i class="fa fa-print"></i> ' + __('Shipping Label'), () => {
                print_shipping_label(frm);
            });
        }

        if (frm.doc.return_shipping_label) {
            frm.add_custom_button('<i class="fa fa-print"></i> ' + __('Return Label'), () => {
                print_return_shipping_label(frm);
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
            frm.add_custom_button(__("Return Shipment"), () => create_return_shipment(frm), __("Create"));

            if (frm.doc.docstatus == 1 && !frm.doc.return_shipping_label) {
                frm.add_custom_button(__('Return Label') + ' <i class="fa fa-exchange"></i>', () => {
                    request_return_label(frm);
                }, __("Create"));
            }

            // Backup location for this function
            if (frm.doc.docstatus == 1 && frm.doc.packing_stage != "Shipped") {
                frm.add_custom_button(__('Request DHL Pickup') + ' <i class="fa fa-truck"></i>', () => {
                    request_pickup(frm);
                }, __("Create"));
            }


        }, 500);

        frm.override_action_buttons()
    },

    before_submit(frm) {
        if (frm.doc.shipment_parcel === undefined || frm.doc.shipment_parcel.length <= 0) {
            frappe.validated = false;
            frappe.msgprint({
                indicator: 'red',
                title: __('Error'),
                message: __('Please enter dimensions and number of Parcels.'),
            });
        }
    },

    add_template(frm) {
        if (frm.doc.parcel_template) {
            frappe.model.with_doc("Shipment Parcel Template", frm.doc.parcel_template, () => {
                let parcel_template = frappe.model.get_doc("Shipment Parcel Template", frm.doc.parcel_template);

                // if last row is empty, use that.
                const lr = frm.doc.shipment_parcel?.slice(-1)[0];
                let row = null;
                if (lr && !lr.length && !lr.width && !lr.height && !lr.weight) {
                    row = lr;
                } else {
                    row = frappe.model.add_child(frm.doc, "Shipment Parcel", "shipment_parcel");
                }

                row.parcel_template_name = parcel_template.parcel_template_name;
                row.length = parcel_template.length;
                row.width = parcel_template.width;
                row.height = parcel_template.height;
                row.weight = parcel_template.weight;
                row.is_pallet = parcel_template.is_pallet;
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

async function custom_mail_dialog(frm) {

    const addr = await frappe.db.get_doc("Address", frm.doc.shipping_address_name || frm.doc.customer_address)
    const recipients = Array.from(new Set([addr.email_id || '', frm.doc.email || '', frm.doc.email_id || '', frm.doc.contact_email || ''].filter(i => i))).join(', ');
    const template_name = await bnovate.utils.get_setting('dn_template') || "Delivery Confirmation";

    var doc = Object.assign({}, frm.doc);
    doc.carrier = frm.doc.carrier || "";
    doc.tracking_no = frm.doc.tracking_no || "";

    return bnovate.utils.email_dialog(frm, template_name, {
        recipients,
        doc,
        attach_print: true,
        print_format: 'Delivery Note',
    });
}

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
    let { same_day_cutoff, pickup_from } = await bnovate.shipping.get_default_times(frm.doc.pallets);
    let pickup_date = frm.doc.posting_date;
    if (pickup_date <= frappe.datetime.now_date()) {
        if (frappe.datetime.now_time() < same_day_cutoff) {
            pickup_date = next_weekday(0);
            pickup_from = moment().add(10, 'minutes').format('HH:mm:ss');
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
        }, {
            label: __("Pickup From"),
            fieldname: "pickup_from",
            fieldtype: "Time",
            reqd: 1,
            default: pickup_from,
        }, {
            label: __("Label Size"),
            fieldname: "label_format",
            fieldtype: "Select",
            options: "8x4 inch\nA4",
            default: "8x4 inch",
            reqd: 1,
        }],
        "Confirm",
        "Cancel",
    )
    return data;
}

async function prompt_label_format(frm) {
    const data = await bnovate.utils.prompt(
        __("Confirm Label Format"),
        [{
            label: __("Label Size"),
            fieldname: "label_format",
            fieldtype: "Select",
            options: "8x4 inch\nA4",
            default: "8x4 inch",
            reqd: 1,
        }],
        "Confirm",
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

async function create_return_shipment(frm) {
    const args = await prompt_label_format(frm);

    if (args === null) {
        return
    }

    frappe.model.open_mapped_doc({
        method: "bnovate.bnovate.utils.shipping.make_return_shipment_from_dn",
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
    frappe.hide_progress()

    console.log(resp.message);
    await frm.reload_doc();

    // Print label directly from return doc to avoid race condition
    const updated_dn = resp.message;
    await print_shipping_label({ doc: updated_dn });
}

// Creates shipment, get shipping label from carrier, DON'T request pickup - leave it to the customer
async function request_return_label(frm) {
    const confirm = await bnovate.utils.confirm_dialog(__("Create return label?"));

    if (confirm === false) {
        console.log("Cancelled");
        return
    }

    const resp = await bnovate.realtime.call({
        method: "bnovate.bnovate.utils.shipping.get_return_label_from_dn",
        args: {
            dn_docname: frm.doc.name,
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
    frappe.hide_progress();

    console.log(resp.message);
    await frm.reload_doc();

    // Print label directly from return doc to avoid race condition
    const updated_dn = resp.message;
    await print_return_shipping_label({ doc: updated_dn });
}


async function print_shipping_label(frm) {
    await bnovate.utils.print_url(frm.doc.shipping_label);
}

async function print_return_shipping_label(frm) {
    await bnovate.utils.print_url(frm.doc.return_shipping_label);
}

function override_action_buttons(frm) {

    if (frm.is_dirty()) {
        return;
    }

    if (frm.doc.docstatus === 1) {
        // Only override action button if form is submitted
        frm.page.clear_primary_action();
        if (frm.doc.packing_stage == "Packing") {

            if (bnovate.shipping.use_auto_ship(frm)) {
                frm.dashboard.add_comment(__("This order can be shipped automatically with DHL") + ` (Incoterm ${frm.doc.incoterm})`);

                frm.page.set_primary_action(__("Ship with DHL") + ' <i class="fa fa-truck"></i>', async () => {
                    return await request_pickup(frm);
                })

            } else {
                frm.dashboard.add_comment(__("Shipping is organized manually on this order") + ` (Incoterm ${frm.doc.incoterm})`);
                frm.page.set_primary_action(__("Request Pickup") + ' <i class="fa fa-paper-plane"></i>', async () => {
                    await frm.set_value({ packing_stage: 'Ready to Ship' });
                    frm.save("Update");
                    await frm.assign();
                })
            }

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
                custom_mail_dialog(frm);
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