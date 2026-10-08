/* Compare.js. (c) 2026, bNovate.
 *
 * Show documents side by side, as they appear in their print preview.
 *
 ****************************************************/

frappe.provide('bnovate.compare');

// Render a document like the print preview of its form (frappe.ui.form.PrintPreview) does: call get_html_and_style
// with the document, the default print format, the letterhead setting and the print language.
// Return { html, style, lang }.
bnovate.compare.get_print_view = async function (doctype, name, print_format) {
    await frappe.model.with_doctype(doctype);
    const doc = await frappe.db.get_doc(doctype, name);
    print_format = print_format || frappe.get_meta(doctype).default_print_format || 'Standard';

    // Same language rules as the print preview
    let format_language = null;
    if (print_format !== 'Standard') {
        const resp = await frappe.db.get_value('Print Format', print_format, 'default_print_language');
        format_language = resp.message?.default_print_language;
    }
    const lang = format_language || doc.language || frappe.boot.lang;

    const print_settings = await frappe.db.get_value('Print Settings', null, 'with_letterhead');
    const with_letterhead = print_settings.message?.with_letterhead ?? 1;

    const r = await frappe.call({
        method: 'frappe.www.printview.get_html_and_style',
        args: {
            doc,
            print_format,
            no_letterhead: with_letterhead ? 0 : 1,
            _lang: lang,
        },
    });
    return { html: r.message.html, style: r.message.style || frappe.boot.print_css, lang };
}

// Show the print previews of two documents side by side in a large dialog.
// left, right: { doctype, name, print_format (optional, defaults to the doctype's default) }
bnovate.compare.print_views = function ({ title, left, right }) {
    const dialog = new frappe.ui.Dialog({
        title,
        fields: [{ fieldtype: 'HTML', fieldname: 'views' }],
    });

    dialog.$wrapper.find('.modal-dialog').css({ 'max-width': '96vw', 'width': '96vw' });

    const pane = (doc) => `
        <div style="flex: 1 1 0; min-width: 0;">
            <h5 style="margin-top: 0;">
                <a href="${frappe.utils.get_form_link(doc.doctype, doc.name)}" target="_blank">${__(doc.doctype)} ${frappe.utils.escape_html(doc.name)}</a>
                <span class="print-lang text-muted" style="font-weight: normal;"></span>
            </h5>
            <iframe style="width: 100%; height: 75vh; border: 1px solid var(--border-color, #d1d8dd);"></iframe>
        </div>`;

    dialog.fields_dict.views.$wrapper.html(`<div style="display: flex; gap: 12px;">${pane(left)}${pane(right)}</div>`);
    dialog.show();

    // An iframe keeps the styles of the two documents apart, but needs the stylesheets of the desk for the preview to
    // look like the print preview of the form.
    const stylesheets = [...document.querySelectorAll('link[rel="stylesheet"]')]
        .map(link => `<link rel="stylesheet" href="${link.href}">`).join('');

    const frames = dialog.fields_dict.views.$wrapper.find('iframe').toArray();
    [left, right].forEach(async (doc, i) => {
        const view = await bnovate.compare.get_print_view(doc.doctype, doc.name, doc.print_format);
        $(frames[i]).parent().find('.print-lang').text(`(${view.lang})`);
        // Same structure as the print preview, and same layout of the footer (see frappe.ui.form.PrintPreview.show_footer)
        frames[i].srcdoc = `<!doctype html><html><head><meta charset="utf-8">${stylesheets}
            <style>${view.style}</style>
            <style>
                .print-format { display: flex; flex-direction: column; }
                .print-format .page-break { display: flex; flex-direction: column; flex: 1; }
                .print-format #footer-html { display: block !important; order: 1; margin-top: auto; }
            </style>
            </head><body>
            <div class="print-preview-wrapper"><div class="print-preview"><div class="print-format">${view.html}</div></div></div>
            </body></html>`;
    });

    return dialog;
}
