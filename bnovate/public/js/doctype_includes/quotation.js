/* Customisations for Quotation
 * 
 * Included by hooks.py to add client-side code
 * (same effect as writing a custom script)
 * 
 * - Removes legacy Create Subscription action
 * - Download buttons: PDF with a cover page, as quotation or as price list
 * - Blurb (letter printed before the quotation): Enhance button, polishes the text with AI
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
        add_enhance_blurb_button(frm);

        if (!frm.is_new()) {
            add_cover_download_button(frm, 'quotation', 'QTN', __('Download as QTN'));
            add_cover_download_button(frm, 'price_list', __('Price List'), __('Download as Price List'));
        }

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

function add_cover_download_button(frm, kind, label, title) {
    // Same trick as the Delivery Note: a download link inside the button, the button itself only shows a progress message.
    // kind is "quotation" or "price_list", see utils/quotation_cover.py
    const url = frappe.urllib.get_full_url('/api/method/bnovate.bnovate.utils.quotation_cover.download_quotation_pdf?'
        + 'name=' + encodeURIComponent(frm.doc.name)
        + '&kind=' + kind
    );
    const button = frm.add_custom_button(`<a href="${url}" download="${frm.doc.name}.pdf"><i class="fa fa-download"></i> ${label}</a>`, () => {
        frappe.show_progress(__('Preparing PDF...'), 50, 100);
        setTimeout(() => frappe.hide_progress(), 1000);
    });
    button.attr('title', title);
}

// Sparkle button next to the label of the Blurb field, to have the text polished by the AI (see utils/ai.py)
function add_enhance_blurb_button(frm) {
    const field = frm.get_field('blurb');
    if (!field) return;

    let $button = field.$wrapper.find('.bn-enhance-blurb');
    if (!$button.length) {
        $button = $(`<button type="button" class="btn btn-default btn-xs bn-enhance-blurb" style="float: right;"
                title="${__('Let the AI polish this text')}">
            <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor" style="vertical-align: -1px;">
                <path d="M10 6c.7 5.2 2.8 7.3 8 8-5.2.7-7.3 2.8-8 8-.7-5.2-2.8-7.3-8-8 5.2-.7 7.3-2.8 8-8z"/>
                <path d="M19 1c.3 2.5 1.5 3.7 4 4-2.5.3-3.7 1.5-4 4-.3-2.5-1.5-3.7-4-4 2.5-.3 3.7-1.5 4-4z"/>
            </svg> ${__('Enhance')}
        </button>`);
        $button.appendTo(field.$wrapper.find('.clearfix').first());
        $button.on('click', () => enhance_blurb(frm));
    }
    $button.toggle(frm.doc.docstatus === 0);
}

async function enhance_blurb(frm) {
    const previous = frm.doc.blurb || '';
    if (!previous.trim()) {
        frappe.msgprint(__('Please write a few notes in the Blurb first.'));
        return;
    }

    const enhanced = await bnovate.ai.enhance_qtn_blurb(frm.doc);
    if (!enhanced) return;

    await frm.set_value('blurb', enhanced);
    const alert = frappe.show_alert({
        message: __('Blurb enhanced'),
        indicator: 'green',
        body: `<a data-action="undo">${__('Undo')}</a>`,
    }, 10, {
        undo: () => {
            frm.set_value('blurb', previous);
            alert.remove();
        },
    });
}
