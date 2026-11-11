/* ai.js. (c) 2026, bNovate.
 *
 * Client side helpers for the AI features of utils/ai.py. Usage:
 *
 *   const translations = await bnovate.ai.translate(['Hello', 'World'], 'de');
 *   const blurb = await bnovate.ai.enhance_qtn_blurb(frm.doc);
 *
 ****************************************************/

frappe.provide('bnovate.ai');

// Call a whitelisted function of utils/ai.py, with the screen frozen while we wait for the model.
bnovate.ai.call = async function (method, args, message) {
    const resp = await frappe.call({
        method: 'bnovate.bnovate.utils.ai.' + method,
        args,
        freeze: true,
        freeze_message: message || __('Asking the AI...'),
    });
    return resp.message;
}

// Translate a string, or a list or object of strings. The result has the same structure as texts.
bnovate.ai.translate = function (texts, target_lang, source_lang = 'en') {
    return bnovate.ai.call('translate', { texts, target_lang, source_lang }, __('Translating...'));
}

// Fields of a Quotation used to improve its blurb: only send what the server uses.
bnovate.ai.QTN_BLURB_FIELDS = [
    'blurb', 'language', 'customer_name', 'contact_person', 'contact_display', 'customer_address',
    'address_display', 'company', 'sales_contact', 'sales_contact_name',
];

// Return an improved version of the blurb of a Quotation. Works on the form's current values, saved or not.
bnovate.ai.enhance_qtn_blurb = function (doc) {
    const fields = {};
    for (const f of bnovate.ai.QTN_BLURB_FIELDS) {
        fields[f] = doc[f];
    }
    return bnovate.ai.call('enhance_qtn_blurb', { doc: fields }, __('Enhancing the text...'));
}
