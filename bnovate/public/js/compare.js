/* Compare.js. (c) 2026, bNovate.
 *
 * Show documents side by side, as they appear in their print preview, and highlight the differences between them.
 *
 * The differences are computed from the data of the documents (items matched by item code, key fields of the header).
 * They are then marked in the print views, which are what the user reads:
 *  - items found in only one of the documents: the whole row,
 *  - changed values: the cell that holds the value, found by its (numeric) value in the row of the item.
 *
 ****************************************************/

frappe.provide('bnovate.compare');

// Fields compared. Only the fields that exist in both documents are compared.
bnovate.compare.ITEM_FIELDS = ['qty', 'uom', 'price_list_rate', 'discount_percentage', 'rate', 'amount'];
bnovate.compare.HEADER_FIELDS = [
    'currency', 'conversion_rate', 'selling_price_list', 'taxes_and_charges', 'payment_terms_template',
    'net_total', 'total_taxes_and_charges', 'grand_total', 'rounded_total',
];
bnovate.compare.NUMERIC_TOTALS = ['net_total', 'total_taxes_and_charges', 'grand_total', 'rounded_total'];

// Render a document like the print preview of its form (frappe.ui.form.PrintPreview) does: call get_html_and_style
// with the document, the default print format, the letterhead setting and the print language.
// Return { doc, html, style, lang }.
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
    return { doc, html: r.message.html, style: r.message.style || frappe.boot.print_css, lang };
}

/******************************************
 * Differences, from the data of the documents
 ******************************************/

bnovate.compare.same = function (a, b, fieldname) {
    if (typeof a === 'number' || typeof b === 'number') {
        return Math.abs(flt(a) - flt(b)) < (fieldname === 'conversion_rate' ? 1e-6 : 0.005);
    }
    return (a || '') === (b || '');
}

// Compare the items and the header of two documents. Items are matched by item code, in order if repeated.
// Items are returned as { row, nth }: nth is the rank of the item among items with the same code in its document.
bnovate.compare.diff = function (a, b) {
    const ranked = (doc) => {
        const seen = {};
        return (doc.items || []).map(row => ({ row, nth: seen[row.item_code] = (seen[row.item_code] ?? -1) + 1 }));
    };
    const result = { removed: [], added: [], changed: [], header: [] };

    const unmatched = ranked(b);
    for (const item_a of ranked(a)) {
        const i = unmatched.findIndex(item_b => item_b.row.item_code === item_a.row.item_code);
        if (i < 0) {
            result.removed.push(item_a);
            continue;
        }
        const item_b = unmatched.splice(i, 1)[0];
        const fields = bnovate.compare.ITEM_FIELDS.filter(f => !bnovate.compare.same(item_a.row[f], item_b.row[f], f));
        if (fields.length) {
            result.changed.push({ a: item_a, b: item_b, fields });
        }
    }
    result.added = unmatched;

    result.header = bnovate.compare.HEADER_FIELDS.filter(f =>
        (a[f] || b[f]) && !bnovate.compare.same(a[f], b[f], f));
    return result;
}

bnovate.compare.is_empty = (diff) => !(diff.removed.length || diff.added.length || diff.changed.length || diff.header.length);

/******************************************
 * Highlighting in the print views
 ******************************************/

bnovate.compare.STYLE = `
    .bn-diff-removed, .bn-diff-removed > td { background: #fbd5d3 !important; }
    .bn-diff-added, .bn-diff-added > td { background: #d3f0da !important; }
    .bn-diff-changed { background: #ffe97a !important; box-shadow: inset 0 0 0 1px #d9b800; }
`;

// Number in the text of an element, or null if the text is not a number (currency symbols and units are ignored).
bnovate.compare.element_number = function (el) {
    const text = el.textContent.replace(/[A-Za-z€$£¥%\s ]/g, '');
    return /^-?[\d'’.,]+$/.test(text) ? flt(text) : null;
}

bnovate.compare.value_in_element = function (el, value) {
    if (typeof value === 'number') {
        const n = bnovate.compare.element_number(el);
        return n !== null && Math.abs(n - value) < 0.005;
    }
    return !!value && el.textContent.trim().toLowerCase() === String(value).toLowerCase();
}

// Row of the print view that shows an item. The print formats number the lines ("Sr" column) like the idx of the rows, and
// do not necessarily show the item code (e.g. for sub-items), so look for the line number, confirmed by the item code or
// name. Otherwise, the nth row with a cell holding the item code.
bnovate.compare.find_row = function (view, row, nth = 0) {
    const rows = [...view.querySelectorAll('tr')];
    const text = (el) => el.textContent.replace(/\s+/g, ' ').toLowerCase();
    const by_number = rows.find(tr =>
        tr.children.length >= 4
        && tr.children[0].textContent.trim() === String(row.idx)
        && [row.item_code, row.item_name].filter(Boolean).some(s => text(tr).includes(String(s).toLowerCase())));
    if (by_number) {
        return by_number;
    }
    return rows.filter(tr => [...tr.children].some(cell => cell.textContent.trim() === String(row.item_code)))[nth];
}

// Mark the differences in a print view. side is 'a' (left) or 'b' (right) of the diff.
bnovate.compare.highlight = function (view, side, doc, diff) {
    const row_of = (item) => bnovate.compare.find_row(view, item.row, item.nth);

    for (const item of side === 'a' ? diff.removed : diff.added) {
        row_of(item)?.classList.add(side === 'a' ? 'bn-diff-removed' : 'bn-diff-added');
    }

    for (const change of diff.changed) {
        const row = row_of(change[side]);
        if (!row) continue;
        for (const fieldname of change.fields) {
            const cell = [...row.children].find(c =>
                !c.classList.contains('bn-diff-changed') && bnovate.compare.value_in_element(c, change[side].row[fieldname]));
            cell?.classList.add('bn-diff-changed');
        }
    }

    // Totals are found below the last item row
    const last_row = (doc.items || [])
        .map(row => bnovate.compare.find_row(view, row))
        .filter(Boolean)
        .sort((x, y) => (x.compareDocumentPosition(y) & Node.DOCUMENT_POSITION_FOLLOWING) ? -1 : 1)
        .slice(-1)[0];
    if (!last_row) return;
    const below = [...view.querySelectorAll('td, th, span, div, p')].filter(el =>
        !el.children.length
        && (last_row.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING)
        && !last_row.contains(el));
    for (const fieldname of diff.header.filter(f => bnovate.compare.NUMERIC_TOTALS.includes(f))) {
        const el = below.find(e => !(e.closest('td') || e).classList.contains('bn-diff-changed')
            && bnovate.compare.value_in_element(e, doc[fieldname]));
        (el?.closest('td') || el)?.classList.add('bn-diff-changed');
    }
}

/******************************************
 * Summary
 ******************************************/

bnovate.compare.summary_html = function (a, b, diff) {
    const esc = frappe.utils.escape_html;
    const format = (doc, row, fieldname) => {
        const df = frappe.meta.get_docfield(row.doctype, fieldname);
        const value = row[fieldname];
        if (!df) return String(value ?? '');
        return $('<div>').html(frappe.format(value, df, { inline: true }, row)).text() || '';
    };
    const label = (row, fieldname) => esc(__(frappe.meta.get_docfield(row.doctype, fieldname)?.label || fieldname));
    const item_text = (item) => `${esc(item.row.item_code)} ${esc(item.row.item_name || '')} &times; ${item.row.qty}`;

    const lines = [];
    for (const f of diff.header) {
        lines.push(`<b>${label(a, f)}</b>: ${esc(format(a, a, f))} &rarr; ${esc(format(b, b, f))}`);
    }
    for (const item of diff.removed) {
        lines.push(`<span class="bn-legend" style="background:#fbd5d3"></span> ${__('Only on {0}', [__(a.doctype)])}: ${item_text(item)}`);
    }
    for (const item of diff.added) {
        lines.push(`<span class="bn-legend" style="background:#d3f0da"></span> ${__('Only on {0}', [__(b.doctype)])}: ${item_text(item)}`);
    }
    for (const change of diff.changed) {
        const fields = change.fields.map(f =>
            `${label(change.a.row, f)} ${esc(format(a, change.a.row, f))} &rarr; ${esc(format(b, change.b.row, f))}`).join('; ');
        lines.push(`<span class="bn-legend" style="background:#ffe97a"></span> ${esc(change.a.row.item_code)}: ${fields}`);
    }

    if (!lines.length) {
        return `<p class="text-muted">${__('No differences found')}</p>`;
    }
    return `<style>.bn-legend { display: inline-block; width: 10px; height: 10px; border-radius: 2px; }</style>`
        + `<ul style="margin: 0 0 10px 0; padding-left: 18px;">${lines.map(l => `<li>${l}</li>`).join('')}</ul>`;
}

/******************************************
 * Dialog
 ******************************************/

// Show the print previews of two documents side by side in a large dialog, with the differences highlighted.
// left, right: { doctype, name, print_format (optional, defaults to the doctype's default) }
bnovate.compare.print_views = function ({ title, left, right }) {
    const dialog = new frappe.ui.Dialog({
        title,
        fields: [
            { fieldtype: 'HTML', fieldname: 'summary' },
            { fieldtype: 'HTML', fieldname: 'views' },
        ],
    });

    dialog.$wrapper.find('.modal-dialog').css({ 'max-width': '96vw', 'width': '96vw' });

    const pane = (doc) => `
        <div style="flex: 1 1 0; min-width: 0;">
            <h5 style="margin-top: 0;">
                <a href="${frappe.utils.get_form_link(doc.doctype, doc.name)}" target="_blank">${__(doc.doctype)} ${frappe.utils.escape_html(doc.name)}</a>
                <span class="print-lang text-muted" style="font-weight: normal;"></span>
            </h5>
            <iframe style="width: 100%; height: 65vh; border: 1px solid var(--border-color, #d1d8dd);"></iframe>
        </div>`;

    dialog.fields_dict.summary.$wrapper.html(`<p class="text-muted"><i class="fa fa-spinner fa-spin"></i></p>`);
    dialog.fields_dict.views.$wrapper.html(`<div style="display: flex; gap: 12px;">${pane(left)}${pane(right)}</div>`);
    dialog.show();

    // An iframe keeps the styles of the two documents apart, but needs the stylesheets of the desk for the preview to
    // look like the print preview of the form.
    const stylesheets = [...document.querySelectorAll('link[rel="stylesheet"]')]
        .map(link => `<link rel="stylesheet" href="${link.href}">`).join('');
    const frames = dialog.fields_dict.views.$wrapper.find('iframe').toArray();

    (async () => {
        const views = await Promise.all([left, right].map(d => bnovate.compare.get_print_view(d.doctype, d.name, d.print_format)));
        const diff = bnovate.compare.diff(views[0].doc, views[1].doc);
        dialog.fields_dict.summary.$wrapper.html(bnovate.compare.summary_html(views[0].doc, views[1].doc, diff));

        views.forEach((view, i) => {
            $(frames[i]).parent().find('.print-lang').text(`(${view.lang})`);
            frames[i].onload = () => bnovate.compare.highlight(frames[i].contentDocument, i === 0 ? 'a' : 'b', view.doc, diff);
            // Same structure as the print preview, and same layout of the footer (see frappe.ui.form.PrintPreview.show_footer)
            frames[i].srcdoc = `<!doctype html><html><head><meta charset="utf-8">${stylesheets}
                <style>${view.style}</style>
                <style>
                    .print-format { display: flex; flex-direction: column; }
                    .print-format .page-break { display: flex; flex-direction: column; flex: 1; }
                    .print-format #footer-html { display: block !important; order: 1; margin-top: auto; }
                </style>
                <style>${bnovate.compare.STYLE}</style>
                </head><body>
                <div class="print-preview-wrapper"><div class="print-preview"><div class="print-format">${view.html}</div></div></div>
                </body></html>`;
        });
    })();

    return dialog;
}
