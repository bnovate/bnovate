/* ai.js. (c) 2026, bNovate.
 *
 * Client side helpers for the AI features of utils/ai.py. Usage:
 *
 *   const translations = await bnovate.ai.translate(['Hello', 'World'], 'de');
 *   const letter = await bnovate.ai.generate_cover_letter(frm.doc);
 *   const { variants, skipped } = await bnovate.ai.generate_variants(frm.doc);
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

// Return the HTML of the cover letter of a Sales Proposal. Works on the form's current values, saved or not.
// The whole document is sent: the server only reads the fields it needs (see utils/ai.py).
bnovate.ai.generate_cover_letter = function (doc) {
    return bnovate.ai.call('generate_cover_letter', { doc }, __('Writing the cover letter...'));
}

// Describe the variants (the linked quotations) of a Sales Proposal: {variants: [...], skipped: [...]}.
bnovate.ai.generate_variants = function (doc) {
    return bnovate.ai.call('generate_variants', { doc }, __('Describing the variants...'));
}
