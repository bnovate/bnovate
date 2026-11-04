/* Customisations for Quotation
 * 
 * Included by hooks.py to add client-side code
 * (same effect as writing a custom script)
 * 
 * - Removes legacy Create Subscription action
 */

frappe.ui.form.on("Quotation", {
    before_load(frm) {
        frm.dashboard.add_transactions({
            'items': ['Subscription Contract'],
            'label': 'Subscription',
        });
        frm.dashboard.add_transactions({
            'items': ['Service Report'],
            'label': __('Service'),
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
    },
    setup(frm) {
        frm.custom_make_buttons['Subscription'] = 'Make Subscription';
        frm.cscript['Make Subscription'] = function () {
            frappe.model.open_mapped_doc({
                method: "bnovate.bnovate.doctype.subscription_contract.subscription_contract.make_from_quotation",
                frm: cur_frm
            });
        }
    },
    refresh(frm) {
        setTimeout(() => {
            frm.remove_custom_button("Subscription", "Create")
            if (frm.doc.docstatus == 1 && frm.doc.status !== 'Lost') {
                if (!frm.doc.valid_till || frappe.datetime.get_diff(frm.doc.valid_till, frappe.datetime.get_today()) >= 0) {
                    frm.add_custom_button(__('Subscription'),
                        frm.cscript['Make Subscription'], __('Create'));
                }
            };
        }, 500);
    },

    async party_name(frm) {

        if (frm.doc.quotation_to != "Customer") {
            return;
        }

        // Get default discount
        let resp = await frappe.db.get_value("Customer", { name: frm.doc.party_name }, "default_discount");
        const default_discount = resp.message.default_discount || 0;
        frm.set_value("default_discount", default_discount);

        bnovate.utils.set_item_discounts(frm);
    },

    apply_default_discount(frm) {
        bnovate.utils.set_item_discounts(frm);
    },

    custom_shipping_rule(frm) {
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
        } else {
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

frappe.ui.form.on('Quotation Item', {
    async price_list_rate(frm, cdt, cdn) {
        if (frm.doc.ignore_default_discount) {
            return;
        }

        await frappe.model.set_value(cdt, cdn, "discount_percentage", frm.doc.default_discount);
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