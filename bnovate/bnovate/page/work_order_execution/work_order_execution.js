/*
Work Order Execution Page
-------------------------

* D. Watson, 2022

This page provides tools for operators to validate execution of work orders.

The workflow goes:

- Load this page, either from a button on WO or by scanning a QR code
- View key information (required items, links to work instructions, comments)
- When work is done, a couple steps:
	- Click "finish", indicate number of finished parts.
	- Adjust quantities of consumed items, add new ones if needed.
	- Scan batch numbers or serial numbers of components
	- Submit -> Creates stock entry, redirects to "view" state


The main view switches between two tables: read and write (to adjust quantities, enter S/N...)

For serialized items, we force entry of components for one item at a time, so the "Submit" button becomes a "Next" button.
Also, STEs are saved in draft state, to allow scanning serial numbers before closing an enclosure, then submitting after QC.

*/

// TODO: what if same info is submitted / sent twice? <-- From another tab open for example.
// Time tracking: stop tracking on submit? Fail safe, don't stop progress if timer had already finished.
// Consider switching to serialized view if any serialized items are present. It shouldn't happen, but why not.
// Batch input: change to multiselectlist, with get_data fetch possible batches?
// Consider: allow re-working a stock entry. Instead of always building STE from scratch, load existing
// 		one with existing SNs & Batches. Would allow scanning components in several stages, and
// 		SNs wouldn't be lost when redrawing the table after adding additional items.

frappe.require("/assets/bnovate/js/storage.js")
frappe.provide("bnovate.work_order_execution")

frappe.pages['work-order-execution'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Work Order Execution',
		single_column: true,
	});
	bnovate.work_order_execution.page = page; // for easier debugging
	window.page = page;

	const read = Symbol("read");
	const write = Symbol("write");

	const state = {
		work_order_id: null, 		// docname of the current workorder
		work_order_doc: null,  		// contents of the current workorder
		sales_order_doc: null,		// contents of the associated sales order, if any.
		docinfo: null, 				// docinfo[doctype][docname] -> {attachments: []}
		view: read,					// state of the items display: read or write
		ste_doc: null, 				// will contain content of stock entry before submitting.
		ste_docs: [],				// existing stock entries related to the work order
		draft_mode: true,			// if true, create draft STE's instead of submitted docs.
		produce_serial_no: false,	// true if produced item needs a serial number.
		serial_no_remaining: 0,  	// when producing with S/N, loop this many more times
		produce_batch: false,		// true if produced item needs a batch number.
		is_fill: false,				// used to display quick "add item" buttons	
		needs_expiry_date: false,	// when produced item needs an expiry date.
		expiry_date_control: null,	// contains expiry date control if it exists...
		default_shelf_life: 9,		// [months] used to calculate expiry date
		qc_required: false,			// true if item requires QC after production.
		quick_add_items: [],		// these items can be added with one click (for common broken parts during refills for example)
		quick_add_bulk: [],			// one click adds several items defined here (like a mini-BOM)
	}
	bnovate.work_order_execution.state = state;
	window.state = state;

	let form = new frappe.ui.FieldGroup({
		fields: [{
			label: 'Work Order',
			fieldname: 'work_order',
			fieldtype: 'Link',
			options: 'Work Order',
		}, {
			label: '',
			fieldtype: 'Column Break',
		}, {
			label: 'Time tracking',
			fieldname: 'time_tracking',
			fieldtype: 'HTML',
			options: '<div id="time_tracking"></div>',
		}, {
			label: '',
			fieldtype: 'Column Break',
		}, {
			label: '',
			fieldtype: 'Section Break',
		}, {
			label: 'Main',
			fieldname: 'main',
			fieldtype: 'HTML',
			options: '<div id="main"></div>',
		}, {
			label: 'Items',
			fieldname: 'items',
			fieldtype: 'HTML',
			options: '<div id="items"></div>',
		}],
		body: page.body
	});
	form.make();

	const work_order = form.fields_dict.work_order.wrapper;
	const time_content = document.getElementById('time_tracking');
	const main_content = document.getElementById('main');
	const item_content = document.getElementById('items');

	function draw() {
		main_content.innerHTML = frappe.render_template('work_order_execution', {
			doc: state.work_order_doc,
			so: state.sales_order_doc,
			docinfo: state.docinfo,
			attachments: state.attachments,
			bom: state.bom_doc,
			qc_required: state.qc_required,
		});
		time_tracking.innerHTML = "";

		page.clear_primary_action();
		page.clear_secondary_action();

		// Cleanup orphan popovers
		[...document.querySelectorAll('.popover')].forEach(el => $(el).popover('hide'));

		if (state.view == read) {
			page.set_secondary_action(__('Reload'), () => state.load_work_order(state.work_order_id));
			item_content.innerHTML = frappe.render_template('items_read', {
				doc: state.work_order_doc,
				ste_docs: state.ste_docs,
				produce_serial_no: state.produce_serial_no,
				produce_batch: state.produce_batch
			});
			if (state.work_order_doc.docstatus == 1 && state.work_order_doc.status != "Stopped") {
				if (state.remaining_qty > 0) {
					page.set_primary_action(state.draft_mode ? __('Start') : __('Finish'), finish);
				}
				time_tracking.innerHTML = frappe.render_template('time_tracking', {
					doc: state.work_order_doc,
					timing_started: state.timing_started,
					qc_required: state.qc_required,
					in_qc_workstation: state.in_qc_workstation,
				})
			}
			attach_ste_submits();
			attach_print_labels();
			attach_timer_buttons();
		} else if (state.view == write) {
			item_content.innerHTML = frappe.render_template('items_write', {
				doc: state.ste_doc,
				quick_add_items: state.quick_add_items,
				quick_add_bulk: state.quick_add_bulk,
			});
			if (state.serial_no_remaining > 0) {
				page.set_primary_action(`Next (${state.serial_no_remaining})`, validate);
			} else {
				page.set_primary_action(state.draft_mode ? __('Done') : __('Submit'), validate);
			}

			if (state.needs_expiry_date) {
				state.expiry_date_control = draw_expiry_input("#expiry-div");
				document.getElementById("expiry-div").hidden = false;
			} else {
				state.expiry_date_control = null;
			}

			attach_update_state();
			attach_validator();
			attach_enterToTab();
			attach_additional_item_buttons();
			focus_next_input(0);
		}

		let doc = state.work_order_doc;
		page.set_title(`Work Order Execution: ${doc.item_name}`);
		page.set_indicator(
			state.work_order_doc.status,
			// use frappe's built-in indicator colour logic.
			frappe.listview_settings['Work Order'].get_indicator(state.work_order_doc)?.[1]
		);
	}

	function draw_expiry_input(parent_id) {
		// Use frappe API to draw their own date selection box.
		expiry_date_control = frappe.ui.form.make_control({
			parent: page.wrapper.find(parent_id),
			df: { fieldname: 'expiry_date', fieldtype: 'Date' },
			render_input: true
		})

		// form_control is a div with many elements.
		// Find the input element
		let input = expiry_date_control.input
		input.classList.add('required');
		input.dataset.required = true;
		expiry_date_control.set_value(
			state.ste_doc.expiry_date ||
			frappe.datetime.add_months(state.work_order_doc.expected_delivery_date, state.default_shelf_life)
		);

		// change detect bound with attach_update_state doesn't work - repeat here
		// Annoyinlgy this is called twice for each change
		expiry_date_control.$input.on('change', update_ste_doc);

		return expiry_date_control;
	}

	async function refresh(pulse_elements = []) {
		await state.load_work_order(state.work_order_id);


		for (let element of pulse_elements) {
			document.getElementById(element).classList.add("pulse-info");
		}
	}

	// DATA STRUCTURE
	////////////////////////////

	state.load_work_order = async (wo_id) => {
		state.view = read; 				// reset view
		state.work_order_id = wo_id;
		state.sales_order_doc = null;
		state.ste_doc = null;
		state.produce_serial_no = false;
		state.produce_batch = false;
		state.serial_no_remaining = 0;
		state.quick_add_items = [];
		state.quick_add_bulk = [];

		// with_doctype loads default for the doctype, populates listview_settings,
		// giving us status indicators
		await frappe.model.with_doctype('Work Order');
		await frappe.model.with_doctype('Stock Entry');

		// with_doc returns the doc and populates docinfo, giving us attachments. Force refresh
		frappe.model.clear_doc('Work Order', wo_id);
		state.work_order_doc = await frappe.model.with_doc('Work Order', wo_id);
		state.docinfo = frappe.model.docinfo;
		state.remaining_qty = state.work_order_doc.qty - state.work_order_doc.produced_qty;
		if (state.work_order_doc.sales_order) {
			state.sales_order_doc = await frappe.model.with_doc('Sales Order', state.work_order_doc.sales_order)
		}
		state.work_order_doc.serial_no_locations = await bnovate.storage.find_serial_nos(state.work_order_doc.serial_no, false);

		// should we switch to serialized behaviour? (produce one item at a time)
		await fetch_item_details([state.work_order_doc.production_item]);
		state.produce_serial_no = locals["Item"][state.work_order_doc.production_item].has_serial_no;
		// if (state.produce_serial_no) {
		// New in May 2025: always use draft mode. Simpler workflow and easier to assign to QC.
		state.draft_mode = true;
		// } else {
		// state.draft_mode = false;
		// }

		state.produce_batch = locals["Item"][state.work_order_doc.production_item].has_batch_no;

		// do we need an expiry date? For now only FILs need them.
		state.is_fill = is_fill(state.work_order_doc.production_item);
		state.needs_expiry_date = is_fill(state.work_order_doc.production_item);
		state.default_shelf_life = locals["Item"][state.work_order_doc.production_item].stability_in_months || 9;
		state.qc_required = locals["Item"][state.work_order_doc.production_item].qc_required || false;
		state.in_qc_workstation = state.work_order_doc.workstation == await bnovate.utils.get_setting("qc_workstation");

		// inherit_expiry_date_from is allow_on_submit, so the BOM can change after
		// submit - always clear the cache to avoid acting on a stale copy.
		frappe.model.clear_doc('BOM', state.work_order_doc.bom_no);
		state.bom_doc = await frappe.model.with_doc('BOM', state.work_order_doc.bom_no);

		// (re-)load associated stock entries
		state.ste_docs.map(doc => frappe.model.clear_doc('Stock Entry', doc.name));
		let ste_docnames = (await frappe.db.get_list('Stock Entry', {
			fields: ['name'],
			filters: { work_order: wo_id }
		}))
			.map(doc => doc.name)
			.sort();
		state.ste_docs = await Promise.all(ste_docnames.map(name =>
			frappe.model.with_doc('Stock Entry', name)
		))
		for (let doc of state.ste_docs) {
			[doc.indicator_label, doc.indicator_color, ...rest] = frappe.listview_settings['Stock Entry'].get_indicator(doc); // safe, get_indicator always returns a value.
			doc.link = frappe.utils.get_form_link('Stock Entry', doc.name);
			doc.produced_serial_nos = doc.items.find(it => it.item_code == state.work_order_doc.production_item)?.serial_no?.trim().replaceAll("\n", ", ");
			doc.produced_batch = doc.items.find(it => it.item_code == state.work_order_doc.production_item)?.batch_no?.trim().replaceAll("\n", ", ");
			doc.scrap_items = doc.items.filter(it => !it.s_warehouse && it.item_code !== doc.bom_item);
			doc.scrap_serial_nos = doc.items.filter(it => !it.s_warehouse && it.item_code !== doc.bom_item)
				.filter(it => it.serial_no)
				.map(it => it.serial_no.trim().replaceAll("\n", ", ")).
				join(", ");


			// Watch out, we can't attach an array to doc, or we get an error on submit.
			let all_serial_nos = [doc.produced_serial_nos?.split(', ') || [], doc.scrap_serial_nos?.split(', ') || []].flat().filter(x => x);
			await Promise.all(all_serial_nos.map(sn => {
				return !!sn && frappe.model.with_doc('Serial No', sn)
			}));

			doc.extras = {}
			doc.extras.serial_no_data = all_serial_nos.map(sn => ({
				name: sn,
				attachments: !!sn && state.docinfo['Serial No']?.[sn]?.attachments || [],
				link: frappe.utils.get_form_link("Serial No", sn, true, sn),
			}));
		}

		// Load attachments / linked docs
		let item_links = locals["Item"][state.work_order_doc.production_item].links; // Assumes we have this custom table on Item doctype
		state.attachments = [];
		state.attachments.push(
			...state.docinfo['Work Order'][wo_id].attachments || [],
			...state.docinfo['BOM'][state.work_order_doc.bom_no].attachments || [],
			...item_links?.map(link => ({ file_url: link.url, file_name: link.title })) || [],
		);

		// Check time tracking status. If a row with no end_time exists, then timing has started.
		state.timing_started = state.work_order_doc.time_log.map(row => row.end_time).indexOf(undefined) >= 0;

		if (state.is_fill) {
			// Populate quick-add-item buttons. Qties adds additional buttons to quick add the specified number of units.
			const item_codes = [
				{ item_code: "100028", qties: [2, 3, 4] },
				{ item_code: "100029", qties: [] },
				{ item_code: "100068", qties: [2, 3, 4] },
				{ item_code: "100069", qties: [] },
				{ item_code: "100076", qties: [2, 3, 4, 5] },
				{ item_code: "100063", qties: [2, 3, 4, 5] },
				{ item_code: "100084", qties: [2, 3] },
				{ item_code: "100055", qties: [2, 3, 4] },
				{ item_code: "100050", qties: [2, 3, 4] },
				{ item_code: "100051", qties: [] },
				{ item_code: "100054", qties: [] },
			]
			const item_docs = await Promise.all(item_codes.map(item => frappe.model.with_doc("Item", item.item_code)));

			state.quick_add_items = item_docs.map(item => ({
				item_code: item.item_code,
				item_name: item.short_name || item.item_name,
				qties: item_codes.find(ic => ic.item_code == item.item_code)?.qties || [],
			}));

			state.quick_add_bulk = [{
				label: __("4-port valve"),
				minibom_name: '4-port valve',
				items: [
					{ item_code: '100011', qty: 1 },
					{ item_code: '100012', qty: 1 },
					{ item_code: '100052', qty: 4 },
					{ item_code: '100053', qty: 2 }
				],
			}, {
				label: __("5-port valve"),
				minibom_name: '5-port valve',
				items: [
					{ item_code: '101049.02', qty: 1 },
					{ item_code: '101050.02', qty: 1 },
					{ item_code: '100052', qty: 4 },
					{ item_code: '100053', qty: 2 }
				],
			}];
		}

		draw();
	}

	state.load_ste = async function (ste) {
		// Add useful properties and load as state.ste_doc

		ste.title = `Manufacture for ${ste.work_order}`;

		// Attach batch and sn requirements.
		await fetch_item_details(ste.items.map(sti => sti.item_code));
		for (let item of ste.items) {
			item.has_batch_no = locals["Item"][item.item_code].has_batch_no;
			item.has_auto_batch_number = !!locals["Item"][item.item_code].batch_number_series;
			item.needs_batch_input = item.has_batch_no && !item.has_auto_batch_number;
			item.has_serial_no = locals["Item"][item.item_code].has_serial_no;
			item.has_auto_serial_no = locals["Item"][item.item_code].serial_no_series;
			item.needs_serial_input = item.has_serial_no && !item.has_auto_serial_no;
		}
		ste.production_item_entry = ste.items.find(it => it.item_code == state.work_order_doc.production_item);
		ste.required_items = ste.items.filter(i => i.s_warehouse).sort((i_a, i_b) => i_a.idx - i_b.idx);
		ste.scrap_items = ste.items.filter(it => !it.s_warehouse && it.item_code !== state.work_order_doc.production_item);
		// These items exist only as scrap, for example the enclosure of a new cartridge.
		ste.exclusively_scrap_items = ste.scrap_items.filter(s_it => ste.required_items.findIndex(r_it => r_it.item_code == s_it.item_code) < 0);


		ste.additional_items = []; // populated by user, when replacing broken parts on refills for example.

		// Prepare doc for final editing in "write" view
		ste.docstatus = state.draft_mode ? 0 : 1;
		state.ste_doc = ste;
	}

	state.add_additional_item = async function (item_code, qty) {
		// Add items during refurbishing (broken handle...)
		// WARNING: these are not 'threadsafe', _row could have duplicates. Not critical considering the application. 
		if (!state.ste_doc) {
			return;
		}
		if (!state.ste_doc.additional_items) {
			state.ste_doc.additional_items = [];
		}

		let item = await frappe.model.with_doc("Item", item_code);
		let item_defaults = item.item_defaults.find(d => d.company == state.ste_doc.company);
		state.ste_doc.additional_items.push({
			_row: state.ste_doc.additional_items.length,
			item_code: item_code,
			item_name: item.item_name,
			has_batch_no: item.has_batch_no,
			has_serial_no: item.has_serial_no,
			qty: qty,
			s_warehouse: item_defaults.default_warehouse,
			expense_account: item_defaults.expense_account,
			cost_center: item_defaults.buying_cost_center,
		});
	}

	state.remove_additional_item = function (_row) {
		if (!state.ste_doc || !state.ste_doc.additional_items) {
			return;
		}

		const index = state.ste_doc.additional_items.findIndex(it => it._row == _row);
		state.ste_doc.additional_items.splice(index, 1);
	}

	// LOGIC
	////////////////////////////
	async function finish() {
		// Prompts user for finished qty.
		page.clear_primary_action();

		let qty = await prompt_qty(state.remaining_qty);

		if (qty == 0) {
			return;
		}

		if (state.timing_started) {
			stop_time_log(state.work_order_id);
		}

		if (state.produce_serial_no) {
			state.serial_no_remaining = qty - 1;
			return await build_ste(1)
		}
		return await build_ste(qty);
	}

	async function build_ste(qty) {
		// Build stock entry and switch items table from read to write view to allow adjusting qties
		let ste = await frappe.xcall('erpnext.manufacturing.doctype.work_order.work_order.make_stock_entry', {
			'work_order_id': state.work_order_id,
			'purpose': 'Manufacture',
			'qty': qty,
		})

		await state.load_ste(ste);

		state.view = write;
		draw();
	}

	async function validate_inputs() {

		// Enable Submit button only if all required fields have values.
		const required_inputs = [...document.querySelectorAll("[data-required]")];
		let valid = true;
		for (let input of required_inputs) {
			let input_valid = true;
			let error = null;
			let warning = null;
			const value = input.value.trim(); // .toUpperCase();
			if (!value) {
				error = 'Required Field'
			} else {

				if (input.classList.contains("check-serial")) {
					// Check that serial number exists and belongs to correct item
					let serial = await frappe.model.with_doc("Serial No", value.toUpperCase());
					if (!serial) {
						error = "Serial No does not exist";
					} else if (serial.item_code !== input.dataset.item) {
						error = `Serial No is for item code ${serial.item_code}!`
					} else if (state.work_order_doc.serial_no && state.work_order_doc.serial_no.toUpperCase().indexOf(value.toUpperCase()) < 0) {
						error = "Does not match work order instructions";
					}


				} else if (input.classList.contains("check-batch")) {
					// Check that batch exists and belongs to correct item
					let batch = await frappe.model.with_doc("Batch", value);
					if (!batch) {
						error = "Batch does not exist";
					} else if (batch.item !== input.dataset.item) {
						error = `Batch is for item code ${batch.item}!`
					}
				}
			}

			$(input).popover('destroy');
			if (error) {
				if (value) {
					// don't show popover for empty field to avoid visual clutter.
					$(input).popover({
						content: `<span class="text-danger">${error}</span>`,
						html: true,
						container: '#page-work-order-execution',
					}).popover('show');

				}
				valid = false;
				input.classList.add('required');
			} else if (warning) {
				$(input).popover({
					content: `<span class="text-warning">${warning}</span>`,
					html: true,
					container: '#page-work-order-execution',
				}).popover('show');
				input.classList.remove('required');
			} else {
				input.classList.remove('required');
			}
		}

		return valid;
	}

	async function validate() {
		// Calls submit() if form is valid. Else shows alert.
		page.btn_primary.prop("disabled", true);

		if (! await validate_inputs()) {
			page.btn_primary.prop("disabled", false);
			frappe.msgprint({
				title: 'Missing or Incorrect Fields',
				indicator: 'red',
				message: 'Please check required fields',
			});
			return;
		}

		submit();
	}

	// Copy form data into state
	async function update_ste_doc() {

		// Get adjusted quantities, keep to the side for now 
		[...document.querySelectorAll("input.qty-delta")]
			.map(el => [el.dataset.idx, el.dataset.item, parseFloat(el.value) || 0])
			.map(([idx, item, delta]) => {
				state.ste_doc.items.find(i => i.idx == idx && i.item_code == item).delta = delta;
			});
		// Same for batches, only on select items.
		[...document.querySelectorAll("input.batch")]
			.map(el => {
				let { idx, row, item } = el.dataset;
				let batch_no = el.value || '';

				if (idx) {  // main items
					state.ste_doc.items.find(i => i.idx == idx && i.item_code == item).batch_no = batch_no.trim();
				}

				if (row) { // additional item
					state.ste_doc.additional_items.find(i => i._row == row && i.item_code == item).batch_no = batch_no.trim();
				}
			}); // BTW, this also modifies the same object pointed to from production_item_entry.
		// And for serial no
		[...document.querySelectorAll("input.serial")]
			// TODO adapt for serial no on additional items.
			.map(el => {
				let { idx, row, item } = el.dataset;
				let serial_no = el.value || '';

				if (idx) {  // main items
					// scrap items can have the same index as input items, need to double-check item_code.
					state.ste_doc.items.find(i => i.idx == idx && i.item_code == item).serial_no = serial_no.toUpperCase().trim();
				}

				if (row) { // additional item
					state.ste_doc.additional_items.find(i => i._row == row && i.item_code == item).serial_no = serial_no.toUpperCase().trim();
				}
			})
		// Comment
		state.ste_doc.comment = document.querySelector("textarea#comment")?.value || null;

		// Handle expiry date if relevant
		if (state.needs_expiry_date && state.expiry_date_control) {
			state.ste_doc.expiry_date = state.expiry_date_control.get_value();
		}

	}

	async function submit() {
		// Submits STE with adjusted qties to db (or saves if draft mode is active).
		page.clear_primary_action();

		update_ste_doc();

		// Adjust quantities
		state.ste_doc.items.forEach(item => item.qty += item.delta || 0);

		if (state.ste_doc.production_item_entry.has_batch_no) {
			// Create target batch if it doesn't exist
			let inherited_expiry_date = await get_inherited_expiry_date(state.ste_doc, state.bom_doc);
			let batch_doc = await get_or_create_batch(state.work_order_doc.production_item,
				state.ste_doc.production_item_entry.batch_no, inherited_expiry_date);

			// Actually fill the field in the case of auto-numbered batches
			if (state.ste_doc.production_item_entry.has_auto_batch_number) {
				state.ste_doc.production_item_entry.batch_no = batch_doc.batch_id;
			}
		}

		if (state.ste_doc.production_item_entry.has_auto_serial_no) {
			// Create SN for production item and fill field (assumes we are only creating one SN at a time.)
			let new_sn = await create_serial_number(state.ste_doc.production_item_entry.item_code);
			state.ste_doc.production_item_entry.serial_no = new_sn;
		}

		// Create SNs for new enclosures if relevant
		for (let scrap_item of state.ste_doc.exclusively_scrap_items) {
			if (scrap_item.has_auto_serial_no) {
				let new_sn = await create_serial_number(scrap_item.item_code);
				scrap_item.serial_no = new_sn
			}
		}

		// Copy over additional items:
		while (state.ste_doc.additional_items.length) {
			let item = state.ste_doc.additional_items.pop();
			state.ste_doc.items.push({
				item_code: item.item_code,
				batch_no: item.batch_no,
				serial_no: item.serial_no,
				// idx: item.idx, // don't copy over idx, it will be recalculated on save.
				qty: item.qty,
				s_warehouse: item.s_warehouse,
				expense_account: item.expense_account,
				cost_center: item.cost_center,
			});
		}


		state.ste_doc.production_item_entry.basic_rate = 1 // Fix a bug where save_doc fails if it's the first time this item was created. The basic rate will be overwritten in calculate_product_valuation.
		set_scrap_item_value(state.ste_doc, state.work_order_doc.production_item);
		// Save to update costs of additional items, set docname...
		await state.load_ste(await save_doc(state.ste_doc));

		handle_scrap(state.ste_doc, state.work_order_doc.production_item);
		handle_warehouses(state.ste_doc, state.work_order_doc);
		await handle_fills(state.ste_doc, state.work_order_doc.production_item);
		calculate_product_valuation(state.ste_doc, state.work_order_doc.production_item);

		// Post comment (saved doc has a docname)
		let comment = document.getElementById("comment").value;
		if (comment) {
			await Promise.all([
				post_comment(state.ste_doc.doctype, state.ste_doc.name, comment),
				post_comment(state.work_order_doc.doctype, state.work_order_doc.name, comment),
			]);
		}

		if (state.draft_mode) {
			await save_doc(state.ste_doc);
		} else {
			await submit_doc(state.ste_doc);
		}
		frappe.show_alert(`<a href="#Form/Stock Entry/${state.ste_doc.name}">${state.ste_doc.name} created</a>`)

		if (state.serial_no_remaining > 0) {
			state.serial_no_remaining -= 1;
			return await build_ste(1);
		}
		// Reload, flash new produced qty
		refresh(["produced-qty"]);
	}

	function handle_scrap(ste_doc, bom_item) {
		// Cleans up exceptions related to scrap items.
		// Finds scrap items with matching SNs in 'input' items and copies SN over

		let scrap_items = ste_doc.items.filter(it => !it.s_warehouse && it.item_code !== bom_item);
		let input_items = ste_doc.items.filter(it => !!it.s_warehouse);

		for (let scrap_item of scrap_items) {
			let input_SNs = input_items
				.filter(it => it.item_code == scrap_item.item_code)
				.map(it => it.serial_no)
				.join("\n");
			if (input_SNs) {
				scrap_item.serial_no = input_SNs
			}
		}
	}

	function handle_warehouses(ste_doc, wo_doc) {
		// make sure warehouses in STE match those of WO
		for (let ste_it of ste_doc.items) {
			if (!ste_it.s_warehouse) {
				continue;
			}
			ste_it.s_warehouse = wo_doc.required_items.find(wo_it => wo_it.item_code == ste_it.item_code)?.source_warehouse || ste_it.s_warehouse;
		}
	}

	async function handle_fills(ste_doc, bom_item) {
		// Handles special workflows related to fills refills
		// - builds "fill associations" table.
		// - removes ENC from storage if applicable
		// Assumes all serial numbers are filled in ste_doc.items.

		if (!is_fill(bom_item)) {
			return;
		}

		let enc_sn = ste_doc.items.find(it => !it.s_warehouse && is_enclosure(it.item_code))?.serial_no;
		let fill_sn = ste_doc.items.find(it => !it.s_warehouse && it.item_code == bom_item)?.serial_no;

		await bnovate.storage.remove_serial_no(enc_sn, false, null, true);

		if (enc_sn && fill_sn) {
			ste_doc.fill_associations = [{
				enclosure_serial_data: enc_sn,
				fill_serial_data: fill_sn,
			}];
		}

	}

	async function prompt_qty(default_qty) {
		return new Promise((resolve, reject) => {
			let d = new frappe.ui.Dialog({
				title: "Enter number of produced items",
				fields: [{
					'fieldname': 'qty',
					'fieldtype': 'Float',
					'label': 'Quantity',
					'default': default_qty,
					// 'options': 'Serial No',
					'reqd': 1,
				}],
				primary_action_label: 'OK',
				primary_action: function (values) {
					resolve(values.qty);
					this.hide();
				},
				secondary_action_label: 'Cancel',
				secondary_action: function () {
					reject();
					draw();
				}
			});
			d.show();
		})
	}

	async function prompt_additional_item() {
		return new Promise((resolve, reject) => {
			let d = new frappe.ui.Dialog({
				title: "Enter additional item",
				fields: [{
					fieldname: 'item_code',
					fieldtype: 'Link',
					label: 'Item code',
					options: 'Item',
					reqd: 1,
				}, {
					fieldname: 'qty',
					fieldtype: 'Float',
					label: 'Quantity',
					reqd: 1,
				}],
				primary_action_label: 'Add',
				primary_action: async function (values) {
					await state.add_additional_item(values.item_code, values.qty);
					resolve(values);
					this.hide();
				},
				secondary_action_label: 'Cancel',
				secondary_action: function () {
					reject();
				}
			})
			d.show();
		});
	}

	function set_scrap_item_value(doc, bom_item) {
		// Sets scrap items rate to 0.01 CHF. Need to save after this to recalculate amount / basic amount
		let scrap_items = doc.items.filter((it) => !it.s_warehouse && it.item_code !== bom_item);
		for (let it of scrap_items) {
			if (is_enclosure(it.item_code)) {
				it.basic_rate = 0.01;
				it.basic_amount = flt(flt(it.transfer_qty) * flt(it.basic_rate), precision("basic_amount", it))
			}
		}
	}
	bnovate.work_order_execution.set_scrap_item_value = set_scrap_item_value;


	function calculate_product_valuation(doc, bom_item) {
		// WARNING: this code is duplicated in custom script on Stock Entry! Manually make changes in both places.
		// Assumes a custom field 'bom_item' exists, that points to the item the BOM manufactures.

		// Before calling this, call set_scrap_item_value, then save the doc to recalculate fields on server-side!

		// Set scrap enclosures to 1 cent, this will send all product value to the fill item, which then goes to COGS.
		let scrap_items = doc.items.filter((it) => !it.s_warehouse && it.item_code !== bom_item);
		let target_items = doc.items.filter((it) => it.item_code === bom_item);
		let input_items = doc.items.filter((it) => !!it.s_warehouse);

		// amount is total CHF value of all items in the filtered list
		let input_amount = input_items.reduce((c, n) => c + n.amount, 0);
		let scrap_amount = scrap_items.reduce((c, n) => c + n.amount, 0);
		let product_qty = target_items.reduce((c, n) => c + n.qty, 0); // should be safer than taking 'For quantity'
		let product_rate = (input_amount - scrap_amount) / product_qty;

		if (product_rate <= 0) {
			console.log("Scrap items are worth more than total input items, aborting valuation calculation.");
			return; // and hope ERPNext will raise an error!
		}

		console.log(`Setting product rate to ${product_rate}. Input amount: ${input_amount}, scrap amount: ${scrap_amount}, qty: ${product_qty}`)
		for (let it of target_items) {
			it.basic_rate = product_rate;
			it.basic_amount = flt(flt(it.transfer_qty) * flt(it.basic_rate), precision("basic_amount", it))
		}
	};
	bnovate.work_order_execution.calculate_product_valuation = calculate_product_valuation;



	// HELPERS
	////////////////////////////
	function is_fill(item_code) {
		return bnovate.utils.is_fill(item_code);
	}

	function is_enclosure(item_code) {
		return bnovate.utils.is_enclosure(item_code);
	}


	// SERVER CALLS
	////////////////////////////

	async function post_comment(doctype, docname, comment) {
		await frappe.call({
			method: "frappe.desk.form.utils.add_comment",
			args: {
				reference_doctype: doctype,
				reference_name: docname,
				content: comment,
				comment_email: frappe.session.user,
				comment_by: frappe.session.user_fullname,
			}
		});
	}

	async function save_doc(doc) {
		let resp = await frappe.call({
			method: "frappe.desk.form.save.savedocs",
			args: {
				doc,
				action: 'Save',
			}
		});
		return resp.docs[0];
	}
	bnovate.work_order_execution.save_doc = save_doc;


	async function submit_doc(doc) {
		let resp = await frappe.call({
			method: "frappe.client.submit",
			args: {
				doc,
			}
		});
		bnovate.utils.confetti();
		return resp.message;
	}
	bnovate.work_order_execution.submit_doc = submit_doc;


	async function start_time_log(work_order_id) {
		let resp = await frappe.call({
			method: "bnovate.bnovate.page.work_order_execution.work_order_execution.start_log",
			args: {
				work_order_id,
			}
		});
		return resp.message;
	}
	bnovate.work_order_execution.start_time_log = start_time_log;


	async function stop_time_log(work_order_id) {
		let resp = await frappe.call({
			method: "bnovate.bnovate.page.work_order_execution.work_order_execution.stop_log",
			args: {
				work_order_id,
			}
		});
		return resp.message;
	}
	bnovate.work_order_execution.stop_time_log = stop_time_log;

	async function assign_qc(work_order_id) {
		let resp = await frappe.call({
			method: "bnovate.bnovate.page.work_order_execution.work_order_execution.assign_qc",
			args: {
				work_order_id,
			}
		});
		return resp.message;
	}


	async function fetch_item_details(item_codes) {
		// Fetch item detail docs, store in locals["Items"].
		let promises = [];
		for (let item_code of item_codes) {
			promises.push(frappe.model.with_doc("Item", item_code));
		}

		return Promise.all(promises);
	}

	async function get_or_create_batch(item_code, batch_no, expiry_date) {
		// Creates batch if it doesn't exist yet.
		// If no batch name is specified, let ERPNext decide it 
		// (only works for items where that option is set)
		// If expiry_date is given, it overrides ERPNext's automatic shelf-life calculation
		// (used for BOMs configured to inherit expiry date from a consumed input item).
		if (!batch_no) {
			return await frappe.db.insert({
				doctype: "Batch",
				item: item_code,
				...(expiry_date && { expiry_date }),
			});
		}

		let batch_doc = await frappe.model.with_doc("Batch", batch_no);
		if (batch_doc) {
			return batch_doc
		}

		return await frappe.db.insert({
			doctype: "Batch",
			title: `${batch_no} for item ${item_code}`,
			batch_id: batch_no,
			item: item_code,
			...(expiry_date && { expiry_date }),
		})
	}

	async function get_inherited_expiry_date(ste_doc, bom_doc) {
		// If the BOM specifies an item to inherit the expiry date from, find the batch(es)
		// consumed for that item in this stock entry and return the earliest of their expiry
		// dates. Returns null if inheritance isn't configured, the item wasn't actually
		// consumed, or none of its batches have an expiry date - in all these cases the
		// caller should fall back to ERPNext's default (shelf-life-based) behaviour.
		let reagent_item = bom_doc.inherit_expiry_date_from;
		if (!reagent_item) {
			return null;
		}

		let consumed_rows = [...ste_doc.items, ...ste_doc.additional_items]
			.filter(it => it.s_warehouse && it.item_code == reagent_item);

		let batch_nos = consumed_rows
			.flatMap(it => (it.batch_no || "").split("\n"))
			.map(b => b.trim())
			.filter(x => !!x);

		let batch_docs = await Promise.all(batch_nos.map(b => frappe.model.with_doc("Batch", b)));
		let expiry_dates = batch_docs
			.map(b => b?.expiry_date)
			.filter(x => !!x);

		if (!expiry_dates.length) {
			return null;
		}

		console.log(`Inherited expiry date for ${reagent_item} is ${expiry_dates.sort()[0]}`)

		return expiry_dates.sort()[0]; // earliest expiry date, ISO date strings sort lexicographically
	}

	async function create_serial_number(item_code) {
		// Creates a new serial number for the given item code. Returns name of SN.
		// Requires a naming series to be set.
		const resp = await frappe.call({
			method: "bnovate.bnovate.page.work_order_execution.work_order_execution.make_auto_serial_no",
			args: {
				item_code
			},
		});
		return resp.message;
	};
	bnovate.work_order_execution.create_serial_number = create_serial_number;

	// LISTENERS
	////////////////////////////

	function attach_update_state() {
		[
			...document.querySelectorAll('div[data-fieldname="items"] input'),
			...document.querySelectorAll('div[data-fieldname="items"] textarea'),
		].map(el => el.addEventListener("change", update_ste_doc));
	}

	function attach_validator() {
		[...document.querySelectorAll("[data-required]")]
			.map(el => el.addEventListener("change", validate_inputs));
	}

	function attach_enterToTab() {
		[...document.querySelectorAll("input")]
			.map(el => el.addEventListener("keydown", event => {
				if (event.key === "Enter") {
					// Find input with next highest tabIndex.
					focus_next_input(event.target.tabIndex);
					event.preventDefault();
				}
			}));
	}

	// Focus input with next highest tabIndex (set tabIndex=0 to focus first input)
	function focus_next_input(tabIndex) {
		let nextInput = [...document.querySelectorAll("input")]
			.filter(el => el.tabIndex > tabIndex)
			.sort((el1, el2) => el1.tabIndex - el2.tabIndex)[0];
		nextInput?.focus();
	}

	function attach_ste_submits() {
		let submit_buttons = [...document.querySelectorAll('.submit-ste')];

		submit_buttons
			.map(el => el.addEventListener('click', async event => {
				submit_buttons.map(el => el.disabled = true); // forbid concurrent submission.
				let doc = state.ste_docs.find(doc => doc.name == el.dataset.docname);
				try {
					if (doc) {
						await submit_doc(doc);
					}
				} finally {
					refresh();
				}
			}));
	}

	function attach_print_labels() {
		[...document.querySelectorAll('.print-rating-plate')]
			.map(el => el.addEventListener('click', event => {
				bnovate.utils.get_label("Stock Entry", el.dataset.docname, "Rating Plate from Stock Entry", "Rating Plate 42x42mm")
			}));

		[...document.querySelectorAll('.print-wo-label')]
			.map(el => el.addEventListener('click', event => {
				bnovate.utils.get_label("Stock Entry", el.dataset.docname, "Work Order Label", "Labels 100x30mm")
			}));

		[...document.querySelectorAll('.print-pouch-label')]
			.map(el => el.addEventListener('click', event => {
				bnovate.utils.get_label("Stock Entry", el.dataset.docname, "Pouch Label", "Labels 30x49mm (4 per row)")
			}));
	}

	function attach_additional_item_buttons() {
		const add_button = document.querySelectorAll('.add-items')[0];
		if (add_button) {
			add_button.addEventListener('click', async event => {
				await prompt_additional_item();
				draw();
			});
		}

		[...document.querySelectorAll('.quick-add-item')]
			.map(el => el.addEventListener('click', async event => {
				let item_code = el.dataset.item;
				let qty = el.dataset.qty ? parseFloat(el.dataset.qty) : 1;
				await state.add_additional_item(item_code, qty);
				draw();
			}));

		[...document.querySelectorAll('.quick-add-bulk')]
			.map(el => el.addEventListener('click', async event => {
				let minibom_name = el.dataset.minibom;
				let minibom = state.quick_add_bulk.find(item => item.minibom_name == minibom_name);

				for (let item of minibom.items) {
					await state.add_additional_item(item.item_code, item.qty);
				}
				draw();
			}));

		[...document.querySelectorAll('.remove-additional-item')]
			.map(el => el.addEventListener('click', async event => {
				await state.remove_additional_item(el.dataset.row);
				draw();
			}));

	}

	function attach_timer_buttons() {
		// And QC buttons since they are in the same box...
		const start_button = document.querySelectorAll('.start-timer')[0];
		if (start_button) {
			start_button.addEventListener('click', async event => {
				await start_time_log(state.work_order_id);
				refresh();
			});
		}

		const stop_button = document.querySelectorAll('.stop-timer')[0];
		if (stop_button) {
			stop_button.addEventListener('click', async event => {
				await stop_time_log(state.work_order_id);
				refresh();
			});
		}

		const qc_button = document.querySelectorAll('.assign-qc')[0];
		if (qc_button) {
			qc_button.addEventListener('click', async event => {
				await assign_qc(state.work_order_id);
				refresh();
			});
		}
	}

	work_order.addEventListener("change", (e) => {
		state.load_work_order(e.target.value);
	})

	page.wrapper.on('show', (e) => {
		if (frappe.route_options.work_order) {
			form.set_value('work_order', frappe.route_options.work_order);
			state.load_work_order(frappe.route_options.work_order)
		}
	});

}