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
    message = message || __('Asking the AI...');
    const request = frappe.call({
        method: 'bnovate.bnovate.utils.ai.' + method,
        args,
        freeze: true,
        freeze_message: message,
    });

    // From the row of a table that is open for editing, Frappe has already frozen the page (behind the row, and without a
    // message): our freeze then only adds to a counter, and nothing shows. Put that freeze in front, with our message, for the
    // time of the call.
    const $freeze = $('#freeze');
    const $message = $freeze.find('.lead');
    const message_added = !$message.text();
    if (message_added) $message.text(message);
    $freeze.css('z-index', 1060);
    try {
        const resp = await request;
        return resp.message;
    } finally {
        $freeze.css('z-index', '');
        if (message_added) $message.text('');
    }
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

// Cost simulation of a quotation (initial investment and running costs, as quoted): {html, unclassified: [...]}.
// strict: false to get {empty: 1} for a quotation without expense categories, instead of an error.
bnovate.ai.generate_cost_simulation = function (quotation, language, strict = true) {
    return bnovate.ai.call('generate_cost_simulation', { quotation, language, strict: strict ? 1 : 0 }, __('Calculating the cost simulation...'));
}
