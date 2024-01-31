/* Customisations for Work Order
 * 
 * Included by hooks.py to add client-side code
 * 
 * - Set target warehouse to Quality Control if inspection needed
 * Note that we hide the default ERPNext inspection system and use "QC required" instead.
 */


frappe.ui.form.on("Work Order", {

    async validate(frm) {
        await frm.events.auto_set_warehouse(frm);
    },


    // Only set warehouse if the field is empty
    async auto_set_warehouse(frm) {
        // Get qc_needed from item - value in form itself isn't always updated at this point in the cycle.
        const item = await frappe.model.with_doc("Item", frm.doc.production_item);
        if (item.qc_required) {
            await frm.events.set_qc_warehouse(frm);
        } else {
            await frm.events.unset_qc_warehouse(frm);
        }
    },

    // Set target warehouse to the QC warehouse
    async set_qc_warehouse(frm) {
        const qc_warehouse = await frappe.db.get_single_value("bNovate Settings", "qc_warehouse");

        frm.doc.fg_warehouse = qc_warehouse;
        frm.refresh_field("fg_warehouse");
    },

    // Reset target warehouse to item default
    async unset_qc_warehouse(frm) {

        const item = await frappe.model.with_doc("Item", frm.doc.production_item);
        const warehouse = item.item_defaults.find(i => i.company == frm.doc.company)?.default_warehouse;

        frm.doc.fg_warehouse = warehouse || null;
        frm.refresh_field("fg_warehouse");
    }
})