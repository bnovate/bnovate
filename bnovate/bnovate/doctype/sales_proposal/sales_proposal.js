// Copyright (c) 2026, bnovate, libracore and contributors
// For license information, please see license.txt

frappe.ui.form.on('Sales Proposal', {
	setup(frm) {
		frm.set_query('customer_address', () => ({
			query: 'frappe.contacts.doctype.address.address.address_query',
			filters: { link_doctype: 'Customer', link_name: frm.doc.customer },
		}));

		frm.set_query('contact_person', () => ({
			query: 'frappe.contacts.doctype.contact.contact.contact_query',
			filters: { link_doctype: 'Customer', link_name: frm.doc.customer },
		}));

		// The quotations of this customer, most recent first. The search also looks into the items of the quotations.
		frm.set_query('quotation', 'quotations', (doc) => ({
			query: 'bnovate.bnovate.doctype.sales_proposal.sales_proposal.quotation_query',
			filters: { customer: doc.customer },
		}));
	},

	onload(frm) {
		// A dot in front of each linked quotation, with the colour and the label of the Quotation list
		frm.set_indicator_formatter('quotation',
			row => quotation_indicator(frm, row.quotation)[1],
			row => {
				const indicator = quotation_indicator(frm, row.quotation);
				return indicator[0] ? `${row.quotation} (${indicator[0]})` : row.quotation;
			}
		);
	},

	refresh(frm) {
		if (!frm.is_new()) {
			add_download_button(frm);
		}

		show_opportunity_link(frm);
		add_sparkle(frm, 'generate_letter');
		add_sparkle(frm, 'generate_variants');
	},

	opportunity_link(frm) {
		show_opportunity_link(frm);
	},

	generate_letter(frm) {
		// the button above the Letter
		write_letter(frm);
	},

	generate_variants(frm) {
		// the button above the Linked Quotations
		write_variants(frm);
	},

	async customer(frm) {
		if (!frm.doc.customer) {
			return;
		}

		const previous_name = frm.doc.customer_name;
		const resp = await frappe.call({
			method: 'bnovate.bnovate.doctype.sales_proposal.sales_proposal.get_customer_details',
			args: { customer: frm.doc.customer },
		});

		const details = resp.message;
		if (!details) {
			return;
		}

		// Keep a title that was typed by hand
		if (!frm.doc.title || frm.doc.title === previous_name) {
			details.title = details.customer_name;
		}
		if (frm.doc.language) {
			delete details.language;
		}
		await frm.set_value(details);
	},

	customer_address(frm) {
		erpnext.utils.get_address_display(frm, 'customer_address');
	},

	async contact_person(frm) {
		if (!frm.doc.contact_person) {
			return;
		}

		const resp = await frappe.call({
			method: 'frappe.contacts.doctype.contact.contact.get_contact_details',
			args: { contact: frm.doc.contact_person },
		});
		const contact = resp.message;
		if (contact) {
			await frm.set_value({
				contact_display: contact.contact_display,
				contact_mobile: contact.contact_mobile,
				contact_email: contact.contact_email,
			});
		}
	},
});

function add_download_button(frm) {
	// Same trick as the Delivery Note: a download link inside the button, the button itself only shows a progress message.
	const url = frappe.urllib.get_full_url('/api/method/bnovate.bnovate.utils.sales_proposal_pdf.download_sales_proposal_pdf?'
		+ 'name=' + encodeURIComponent(frm.doc.name)
	);
	const filename = `${frm.doc.name}.pdf`;
	const button = frm.add_custom_button(`<a href="${url}" download="${filename}"><i class="fa fa-download"></i> ${__('Download PDF')}</a>`, () => {
		frappe.show_progress(__('Preparing PDF...'), 50, 100);
		setTimeout(() => frappe.hide_progress(), 1000);
	});
	button.attr('title', __('Cover page, cover letter, quotations and attached PDFs in one PDF'));

	// The PDF is made from the saved document: save pending changes (a generated cover letter...) before downloading.
	button.find('a').on('click', async (event) => {
		if (!frm.is_dirty()) {
			return;
		}
		event.preventDefault();
		await frm.save();

		const link = document.createElement('a');
		link.href = url;
		link.download = filename;
		document.body.appendChild(link);
		link.click();
		link.remove();
	});
}

// The AI buttons (Button fields) get a sparkle in front of their label
function add_sparkle(frm, fieldname) {
	const $button = frm.get_field(fieldname).$input;
	if (!$button || $button.find('svg').length) return;

	$button.prepend(`<svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor" style="vertical-align: -1px; margin-right: 4px;">
		<path d="M10 6c.7 5.2 2.8 7.3 8 8-5.2.7-7.3 2.8-8 8-.7-5.2-2.8-7.3-8-8 5.2-.7 7.3-2.8 8-8z"/>
		<path d="M19 1c.3 2.5 1.5 3.7 4 4-2.5.3-3.7 1.5-4 4-.3-2.5-1.5-3.7-4-4 2.5-.3 3.7-1.5 4-4z"/>
	</svg>`);
}

// Have the cover letter written by the AI (see utils/ai.py)
async function write_letter(frm) {
	const elements = ['needs_identified', 'solution_proposed', 'benefits_expected'];
	if (!elements.some(fieldname => (frm.doc[fieldname] || '').trim())) {
		frappe.msgprint(__('Please fill in the Proposal Elements first.'));
		return;
	}

	const previous = frm.doc.cover_letter || '';
	const letter = await bnovate.ai.generate_cover_letter(frm.doc);
	if (!letter) return;

	await frm.set_value('cover_letter', letter);
	const alert = frappe.show_alert({
		message: __('Cover letter generated'),
		indicator: 'green',
		body: previous.trim() ? `<a data-action="undo">${__('Undo')}</a>` : '',
	}, 10, {
		undo: () => {
			frm.set_value('cover_letter', previous);
			alert.remove();
		},
	});
}

// Have each quotation described as a variant by the AI
async function write_variants(frm) {
	if (!(frm.doc.quotations || []).some(row => row.quotation)) {
		frappe.msgprint(__('Please add the quotations first.'));
		return;
	}

	const result = await bnovate.ai.generate_variants(frm.doc);
	if (!result) return;

	const regenerated = new Set();
	for (const variant of result.variants) {
		const row = frm.doc.quotations.find(r => r.quotation === variant.quotation);
		if (!row) continue;
		regenerated.add(variant.quotation);
		await frappe.model.set_value(row.doctype, row.name, {
			variant_title: variant.title,
			variant_intro: variant.intro,
			variant_benefits: variant.benefits,
		});
	}

	// Products of the variants that were just written replace the old ones; the others are kept. Rows follow the order of the quotations.
	const fresh = {};
	for (const variant of result.variants) {
		fresh[variant.quotation] = variant.items.map(item => Object.assign({ quotation: variant.quotation }, item));
	}
	const kept = {};
	for (const row of frm.doc.variant_items || []) {
		if (!regenerated.has(row.quotation)) {
			(kept[row.quotation] = kept[row.quotation] || []).push(
				{ quotation: row.quotation, item_code: row.item_code, item_name: row.item_name, description: row.description, image: row.image });
		}
	}
	const items = [];
	for (const row of frm.doc.quotations) {
		items.push(...(fresh[row.quotation] || kept[row.quotation] || []));
		delete fresh[row.quotation];
		delete kept[row.quotation];
	}
	items.push(...Object.values(kept).flat());

	frm.clear_table('variant_items');
	for (const item of items) {
		frm.add_child('variant_items', item);
	}
	frm.refresh_field('quotations');
	frm.refresh_field('variant_items');

	frappe.show_alert({ message: __('Variants generated'), indicator: 'green' }, 10);
	if (result.skipped.length) {
		frappe.msgprint(__('No variant was written for {0}: none of its items has a commercial description.', [result.skipped.join(', ')]));
	}
}

// Status of a linked quotation: [label, colour]. The status comes with the form (see onload() in sales_proposal.py), or
// from the quotation that was just picked. Same labels and colours as the Quotation list (quotation_list.js of ERPNext).
function quotation_indicator(frm, quotation) {
	const q = ((frm.doc.__onload || {}).quotation_status || {})[quotation];
	if (!q) return ['', 'grey'];

	if (q.docstatus === 2 || q.status === 'Cancelled') return [__('Cancelled'), 'red'];
	if (q.docstatus === 0 || q.status === 'Draft') return [__('Draft'), 'red'];
	if (q.status === 'Open') {
		if (q.valid_till && q.valid_till < frappe.datetime.nowdate()) return [__('Expired'), 'darkgrey'];
		return [__('Open'), 'orange'];
	}
	if (q.status === 'Ordered') return [__('Ordered'), 'green'];
	if (q.status === 'Lost') return [__('Lost'), 'darkgrey'];
	if (q.status === 'Expired') return [__('Expired'), 'darkgrey'];
	return [__(q.status), 'blue'];
}

frappe.ui.form.on('Sales Proposal Quotation', {
	async quotation(frm, cdt, cdn) {
		// A quotation was just picked: its status is not in the form yet
		const name = locals[cdt][cdn].quotation;
		if (!name) return;

		const resp = await frappe.db.get_value('Quotation', name, ['name', 'status', 'docstatus', 'valid_till']);
		if (!resp.message) return;

		frm.doc.__onload = frm.doc.__onload || {};
		frm.doc.__onload.quotation_status = frm.doc.__onload.quotation_status || {};
		frm.doc.__onload.quotation_status[name] = resp.message;
		frm.refresh_field('quotations');
	},
});

// Clickable version of the opportunity link, same as on Quote
function show_opportunity_link(frm) {
	const link = (frm.doc.opportunity_link || '').trim();
	const html = /^https?:\/\//i.test(link)
		? `<b>${__('Clickable link:')}</b> <a href="${frappe.utils.escape_html(link)}" target="_blank" rel="noopener">${frappe.utils.escape_html(link)}</a>`
		: '';
	$(frm.fields_dict.opportunity_link_html.wrapper).html(html);
}
