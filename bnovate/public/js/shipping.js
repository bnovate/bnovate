// (C) 2023, bnovate

frappe.provide('bnovate.shipping');

function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
}

// Return last possible time for same-day pickup
bnovate.shipping.get_default_times = async function (pallets) {
    const resp = await frappe.call({
        method: 'bnovate.bnovate.utils.shipping.get_default_times',
        args: {
            pallets
        }
    })
    return resp.message
}

bnovate.shipping.validate_address = async function (name, throw_error = true) {
    try {
        const resp = await frappe.call({
            method: 'bnovate.bnovate.utils.shipping.validate_address',
            args: {
                name,
                throw_error
            }
        });

        if (!throw_error) {
            return !!resp.message;
        }

    } catch (e) {
        // Error message is displayed anyway.
        return;
    }

    // If no error raised, Address is shippable
    frappe.msgprint(__("Address is deliverable"))
}

bnovate.shipping.validate_sales_order = async function (name) {
    const resp = await frappe.call({
        method: 'bnovate.bnovate.utils.shipping.validate_sales_order',
        args: {
            name,
        }
    });
    return resp.message
}


// Attempt to determine if we should auto-ship or not, i.e. ship through the API or manually.
bnovate.shipping.use_auto_ship = function (frm) {

    // Manual override through checkbox
    if (frm.doc.skip_autoship)
        return false;


    // If incoterm is EXW, FCA, or variants of DDP, we don't organize shipping
    if (frm.doc.incoterm == "EXW" || frm.doc.incoterm == "FCA" || frm.doc.incoterm.startsWith("DDP")) {
        return false;
    }

    // Remaining incoterms is DAP.
    // If we specify the carrier, and it's not DHL, then we definitely don't ship through API
    // Example: we ship DAP through a freight carrier.
    if (frm.carrier && frm.carrier !== "DHL")
        return false;

    return true;
}
