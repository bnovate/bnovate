/* Customisations for BOM
 *
 * Included by hooks.py to add client-side code
 *
 * - Restrict "Inherit Expiry Date From" to items already listed in this BOM.
 * - Only show "Inherit Expiry Date From" when the produced item is itself
 *   batch- and expiry-tracked, and at least one input item is expiry-tracked.
 */

frappe.ui.form.on("BOM", {
    refresh(frm) {
        frm.set_query("inherit_expiry_date_from", function () {
            let item_codes = (frm.doc.items || [])
                .map(row => row.item_code)
                .filter(x => !!x);
            return {
                filters: {
                    item_code: ["in", item_codes],
                },
            };
        });

        update_inherit_expiry_date_visibility(frm);
    },
    item(frm) {
        update_inherit_expiry_date_visibility(frm);
    },
    items_add(frm) {
        update_inherit_expiry_date_visibility(frm);
    },
    items_remove(frm) {
        update_inherit_expiry_date_visibility(frm);
    },
});

frappe.ui.form.on("BOM Item", {
    item_code(frm) {
        update_inherit_expiry_date_visibility(frm);
    },
});

async function update_inherit_expiry_date_visibility(frm) {
    let input_items = (frm.doc.items || [])
        .map(row => row.item_code)
        .filter(x => !!x);

    if (!frm.doc.item || !input_items.length) {
        frm.toggle_display("inherit_expiry_date_from", false);
        return;
    }

    let show = await frappe.call({
        method: "bnovate.bnovate.utils.bom.should_show_inherit_expiry_date",
        args: {
            production_item: frm.doc.item,
            input_items,
        },
    }).then(r => !!r.message);

    frm.toggle_display("inherit_expiry_date_from", show);
}
