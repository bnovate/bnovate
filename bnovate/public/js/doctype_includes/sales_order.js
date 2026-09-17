/* Customisations for Sales Order
 * 
 * Included by hooks.py to add client-side code
 * (same effect as writing a custom script)
 * 
 */

frappe.require("/assets/bnovate/js/modals.js")  // provides bnovate.modals
frappe.require("/assets/bnovate/js/shipping.js")  // provides bnovate.shipping

frappe.ui.form.on("Sales Order", {
    async before_load(frm) {
        frm.dashboard.add_transactions({
            'items': ['Refill Request', 'Service Report', 'Subscription Contract'], // check dashboards.py and hooks to complete this!
            'label': 'Reference',
        });

        frm.dashboard.add_transactions({
            'items': ['Shipment'],
            'label': 'Fulfillment',
        });

        // Hijack formatter, we'll set colours according to deliverability later.
        frm.set_indicator_formatter('item_code', (doc) => "");
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

        frm.set_query("blanket_order", "items", function () {
            return {
                filters: {
                    "company": frm.doc.company,
                    "docstatus": 1,
                    "to_date": [">=", frm.doc.transaction_date],
                    "from_date": ["<=", frm.doc.transaction_date],
                    "customer": frm.doc.customer,
                    "currency": ["IN", [frm.doc.currency, ""]]
                }
            }
        });

        if (frm.doc.tc_name && !frm.doc.terms) {
            // Trigger copying of template
            frm.trigger('tc_name');
        }

    },

    async refresh(frm) {
        setTimeout(() => {
            frm.remove_custom_button(__("Subscription"), __("Create"));
        }, 500);

        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Refill Request'),
                function () {
                    erpnext.utils.map_current_doc({
                        method: "bnovate.bnovate.doctype.refill_request.refill_request.make_sales_order",
                        source_doctype: "Refill Request",
                        target: frm,
                        setters: [
                            {
                                label: "Customer",
                                fieldname: "customer",
                                fieldtype: "Link",
                                options: "Customer",
                                default: frm.doc.customer || undefined
                            }
                        ],
                        get_query_filters: {
                            docstatus: 1,
                            status: "Submitted", // Ignore already confirmed orders
                        }
                    })
                }, __("Get items from"));

        }

        frm.add_custom_button(__('Return Shipment'), () => create_return_shipment(frm), __("Create"));

        // Show cartridges owned by this customer in a modal
        bnovate.modals.attach_report_modal("cartStatusModal");
        frm.fields_dict.view_stored_cartridges.wrapper.innerHTML = bnovate.modals.report_link(
            '<button class="btn btn-default btn-xs">View Cartridges</button>',
            'cartStatusModal',
            'Cartridge Status',
            'Catridges owned by this customer',
            {
                'customer': frm.doc.customer
            }

        );

        bnovate.modals.attach_report_modal("projStockModal");
        if (!frm.doc.__islocal) {
            setTimeout(() => show_deliverability(frm), 500);
        }
    },

    async before_submit(frm) {

        // If incoterm requires that we ship, check deliverability:
        if (bnovate.shipping.use_auto_ship(frm)) {
            const err = await bnovate.shipping.validate_sales_order(frm.doc.name);
            if (err.error) {
                frappe.msgprint(err.error + ":<br><br>" + err.message);
                frappe.validated = false;
            }
        }
    },

    after_save(frm) {
        frm.toggle_display('date_change_origin', false);
        frm.set_df_property('date_change_origin', 'reqd', false);
    },

    async customer(frm) {
        // Fetch default terms from customer group
        const customer_doc = await frappe.model.with_doc("Customer", frm.doc.customer);
        const customer_group = await frappe.model.with_doc("Customer Group", customer_doc.customer_group);

        setTimeout(() => {
            frm.set_value('taxes_and_charges', customer_group.taxes_and_charges_template);
        }, 500)

        // Default discount
        frm.set_value("default_discount", customer_doc.default_discount || 0);

        bnovate.utils.set_item_discounts(frm);
    },

    breakbulk_master_no(frm) {
        if (frm.doc.breakbulk_master_no) {
            frm.set_value("skip_autoship", 1);
        }
    },

    apply_default_discount(frm) {
        bnovate.utils.set_item_discounts(frm);
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

    async translate_all(frm) {
        let texts = await frm.doc.items.flatMap(item => [item.item_name, item.description]);
        let translations = await bnovate.utils.deepl_translate(texts, frm.doc.language);

        frm.doc.items.forEach((item, i) => {
            frappe.model.set_value(item.doctype, item.name, "item_name", translations[2 * i]);
            frappe.model.set_value(item.doctype, item.name, "description", translations[2 * i + 1]);
        });
    },
})

frappe.ui.form.on('Sales Order Item', {
    async price_list_rate(frm, cdt, cdn) {
        if (frm.doc.ignore_default_discount) {
            return;
        }

        await frappe.model.set_value(cdt, cdn, "discount_percentage", frm.doc.default_discount);
    },

    delivery_date(frm, cdt, cdn) {
        console.log('Delivery date changed', cdt, cdn);
        if (frm.doc.docstatus === 1) {
            frm.toggle_display('date_change_origin', true);
            frm.set_df_property('date_change_origin', 'reqd', true);
        }
    },

    async translate(frm, cdt, cdn) {
        let item = locals[cdt][cdn];
        let texts = [item.item_name, item.description];

        let translations = await bnovate.utils.deepl_translate(texts, frm.doc.language);

        frappe.confirm(
            __('Are these translations suitable?<br><p><b>Item Name:</b></p> <p>{0}<p> <p><b>Description:</b><p> <p>{1}</p>', [translations[0], translations[1]]),
            function () {
                frappe.model.set_value(cdt, cdn, "item_name", translations[0]);
                frappe.model.set_value(cdt, cdn, "description", translations[1]);
            },
            function () {
                // Do nothing on cancel
            }
        );
    }
})

async function get_deliverability(frm) {
    const report_data = await bnovate.utils.run_report('Orders to Fulfill', { sales_order: frm.doc.name, include_drafts: 1 });
    let d = {}
    for (let row of report_data.result) {
        d[row.detail_docname] = row;
    }
    return d;
}

async function show_deliverability(frm) {
    const deliverability = await get_deliverability(frm);
    for (let item of cur_frm.doc.items) {
        const indicator = document.querySelector(`[data-name="${item.name}"] .indicator`)
        let colour = "darkgrey";
        let planned_stock = "";
        let status = deliverability[item.name];
        if (item.stock_qty <= item.delivered_qty) {
            colour = "light-blue";
        } else if (typeof status !== undefined) {
            colour = ["red", "orange", "yellow", "green"][status.sufficient_stock];
            if (status.guaranteed_stock !== null && status.projected_stock !== null) {
                const stock_field = document.querySelector(`[data-name="${item.name}"] [data-fieldname="planned_stock"]`)
                if (stock_field) {
                    stock_field.innerHTML = `<span class="coloured" style="text-align: center; padding-top: 10px"><a>${status.projected_stock} | ${status.guaranteed_stock}</a></span>`;
                    stock_field.firstChild.addEventListener('click', (event) => {
                        event.stopImmediatePropagation();
                        event.preventDefault();
                        bnovate.modals.show('projStockModal',
                            'Projected Stock',
                            `Projected Stock for Item ${item.item_code}: ${item.item_name}`,
                            {
                                'item_code': item.item_code,
                                'so_drafts': true,
                                // 'warehouse': item.warehouse,
                            }
                        );
                    });
                }
            }
        }
        indicator.classList.add(colour);
    }
}


async function prompt_label_format(frm) {
    const data = await bnovate.utils.prompt(
        __("Confirm Label Format"),
        [{
            label: __("Label Size"),
            fieldname: "label_format",
            fieldtype: "Select",
            options: "8x4 inch\nA4",
            default: "A4",
            reqd: 1,
        }],
        "Confirm",
        "Cancel",
    )
    return data;
}

async function create_return_shipment(frm) {

    const args = await prompt_label_format(frm);
    if (args === null) {
        return
    }

    // Since we allow this on draft, we haven't yet validated the SO for delivery creation
    const err = await bnovate.shipping.validate_sales_order(frm.doc.name);
    if (err.error) {
        frappe.msgprint(err.error + ":<br><br>" + err.message);
        return
    }

    frappe.model.open_mapped_doc({
        method: "bnovate.bnovate.utils.shipping.make_return_shipment_from_so",
        frm,
        args,
    })
}