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


The main view switches between two tables: read and write (to adjust quantities, enter S/N....)

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

frappe.provide("frappe.bnovate.work_order_execution")

frappe.pages['work-order-execution'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Work Order Execution',
		single_column: true,
	});
	frappe.bnovate.work_order_execution.page = page; // for easier debugging
	window.page = page;

	const read = Symbol("read");
	const write = Symbol("write");

	const state = {
		work_order_id: null, 		// docname of the current workorder
		work_order_doc: null,  		// contents of the current workorder
		docinfo: null, 				// docinfo[doctype][docname] -> {attachments: []}
		view: read,					// state of the items display: read or write
		ste_doc: null, 				// will contain content of stock entry before submitting.
		ste_docs: [],				// existing stock entries related to the work order
		draft_mode: false,			// if true, create draft STE's instead of submitted docs.
		produce_serial_no: false,	// true if produced item needs a serial number.
		serial_no_remaining: 0,  	// when producing with S/N, loop this many more times
		produce_batch: false,		// true if produced item needs a batch number.
		needs_expiry_date: false,	// when produced item needs an expiry date.
		expiry_date_control: null,	// contains expiry date control if it exists...
		default_shelf_life: 9,		// [months] used to calculate expiry date
	}
	frappe.bnovate.work_order_execution.state = state;
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
			docinfo: state.docinfo,
			attachments: state.attachments,
		});
		time_tracking.innerHTML = "";

		page.clear_primary_action();
		page.clear_secondary_action();
		if (state.view == read) {
			page.set_secondary_action('Reload', () => state.load_work_order(state.work_order_id));
			item_content.innerHTML = frappe.render_template('items_read', {
				doc: state.work_order_doc,
				ste_docs: state.ste_docs,
				produce_serial_no: state.produce_serial_no,
				produce_batch: state.produce_batch
			});
			if (state.remaining_qty > 0 && state.work_order_doc.docstatus == 1 && state.work_order_doc.status != "Stopped") {
				page.set_primary_action(state.draft_mode ? 'Start' : 'Finish', finish);
				time_tracking.innerHTML = frappe.render_template('time_tracking', {
					doc: state.work_order_doc,
					timing_started: state.timing_started,
				})
			}
			attach_ste_submits();
			attach_print_labels();
			attach_timer_buttons();
		} else if (state.view == write) {
			item_content.innerHTML = frappe.render_template('items_write', {
				doc: state.ste_doc,
			});
			if (state.serial_no_remaining > 0) {
				page.set_primary_action(`Next (${state.serial_no_remaining})`, validate);
			} else {
				page.set_primary_action(state.draft_mode ? 'Done' : 'Submit', validate);
			}

			if (state.needs_expiry_date) {
				state.expiry_date_control = draw_expiry_input("#expiry-div");
				document.getElementById("expiry-div").hidden = false;
			} else {
				state.expiry_date_control = null;
			}

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
		expiry_date_control.set_value(frappe.datetime.add_months(state.work_order_doc.expected_delivery_date, state.default_shelf_life));

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
		state.ste_doc = null;
		state.produce_serial_no = false;
		state.produce_batch = false;
		state.serial_no_remaining = 0;

		// with_doctype loads default for the doctype, populates listview_settings,
		// giving us status indicators
		await frappe.model.with_doctype('Work Order');
		await frappe.model.with_doctype('Stock Entry');

		// with_doc returns the doc and populates docinfo, giving us attachments. Force refresh
		frappe.model.clear_doc('Work Order', wo_id);
		state.work_order_doc = await frappe.model.with_doc('Work Order', wo_id);
		state.docinfo = frappe.model.docinfo;
		state.remaining_qty = state.work_order_doc.qty - state.work_order_doc.produced_qty;

		// should we switch to serialized behaviour? (produce one item at a time)
		await fetch_item_details([state.work_order_doc.production_item]);
		state.produce_serial_no = locals["Item"][state.work_order_doc.production_item].has_serial_no;
		if (state.produce_serial_no) {
			state.draft_mode = true;
		} else {
			state.draft_mode = false;
		}

		state.produce_batch = locals["Item"][state.work_order_doc.production_item].has_batch_no;

		// do we need an expiry date? For now only FILs need them.
		state.needs_expiry_date = is_fill(state.work_order_doc.production_item);
		// state.default_shelf_life = locals["Item"][state.work_order_doc.production_item].shelf_life_in_days <-- days vs months...

		// BOMs can't change after submit, no need to clear cache
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
			qty: qty,
			s_warehouse: item_defaults.default_warehouse,
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

	function validate_inputs() {
		// Enable Submit button only if all required fields have values.
		const required_inputs = [...document.querySelectorAll("[data-required]")];
		let valid = true;
		for (let input of required_inputs) {
			if (!input.value) {
				input.classList.add('required')
				valid = false;
			} else {
				input.classList.remove('required')
			}
		}
		return valid;
	}

	function validate() {
		// Calls submit() if form is valid. Else shows alert.
		page.btn_primary.prop("disabled", true);

		if (!validate_inputs()) {
			page.btn_primary.prop("disabled", false);
			frappe.msgprint({
				title: 'Missing Fields',
				indicator: 'red',
				message: 'Please complete required fields',
			});
			return;
		}

		submit();
	}

	async function submit() {
		// Submits STE with adjusted qties to db.
		page.clear_primary_action();

		// Get adjusted quantities, apply to STE items
		[...document.querySelectorAll("input.qty-delta")]
			.map(el => [el.dataset.idx, parseFloat(el.value) || 0])
			.map(([idx, delta]) => {
				state.ste_doc.items.find(i => i.idx == idx).qty += delta;
			});
		// Same for batches, only on select items.
		[...document.querySelectorAll("input.batch")]
			.map(el => [el.dataset.idx, el.value || 0])
			.map(([idx, batch_no]) => {
				state.ste_doc.items.find(i => i.idx == idx).batch_no = batch_no.trim();
			}); // BTW, this also modifies the same object pointed to from production_item_entry.
		// And for serial no
		[...document.querySelectorAll("input.serial")]
			.map(el => [el.dataset.idx, el.dataset.item, el.value || 0])
			.map(([idx, item, serial_no]) => {
				state.ste_doc.items.find(i => i.idx == idx && i.item_code == item).serial_no = serial_no.trim(); // scrap items can have same index as input items, need to double-check item_code.
			});
		// Handle expiry date if relevant
		if (state.needs_expiry_date && state.expiry_date_control) {
			state.ste_doc.expiry_date = state.expiry_date_control.get_value();
		}

		if (state.ste_doc.production_item_entry.has_batch_no) {
			// Create target batch if it doesn't exist
			let batch_doc = await get_or_create_batch(state.work_order_doc.production_item,
				state.ste_doc.production_item_entry.batch_no);

			// Actually fill the field in the case of auto-numbered batches
			if (state.ste_doc.production_item_entry.has_auto_batch_number) {
				state.ste_doc.production_item_entry.batch_no = batch_doc.batch_id;
			}
		}

		// Copy over additional items:
		while (state.ste_doc.additional_items.length) {
			let item = state.ste_doc.additional_items.pop();
			state.ste_doc.items.push({
				item_code: item.item_code,
				qty: item.qty,
				s_warehouse: item.s_warehouse,
			});
		}


		set_scrap_item_value(state.ste_doc, state.work_order_doc.production_item);
		// Save to update costs of additional items, set docname...
		await state.load_ste(await save_doc(state.ste_doc));

		handle_scrap(state.ste_doc, state.work_order_doc.production_item);
		handle_warehouses(state.ste_doc, state.work_order_doc);
		handle_fills(state.ste_doc, state.work_order_doc.production_item);
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

	function handle_fills(ste_doc, bom_item) {
		// Handles special workflows related to fills refills
		// - builds "fill associations" table.
		// Assumes all serial numbers are filled in ste_doc.items.

		if (!is_fill(bom_item)) {
			return;
		}

		let enc_sn = ste_doc.items.find(it => !it.s_warehouse && it.item_code == "100146")?.serial_no;
		let fill_sn = ste_doc.items.find(it => !it.s_warehouse && it.item_code == bom_item)?.serial_no;

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
	frappe.bnovate.work_order_execution.set_scrap_item_value = set_scrap_item_value;


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
	frappe.bnovate.work_order_execution.calculate_product_valuation = calculate_product_valuation;



	// HELPERS
	////////////////////////////
	function is_fill(item_code) {
		return item_code !== undefined && item_code.startsWith("FIL");
	}

	function is_enclosure(item_code) {
		return item_code !== undefined && (item_code.startsWith("ENC") || item_code === '100146');
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
	frappe.bnovate.work_order_execution.save_doc = save_doc;


	async function submit_doc(doc) {
		let resp = await frappe.call({
			method: "frappe.client.submit",
			args: {
				doc,
			}
		});
		return resp.message;
	}
	frappe.bnovate.work_order_execution.submit_doc = submit_doc;


	async function start_time_log(work_order_id) {
		let resp = await frappe.call({
			method: "bnovate.bnovate.page.work_order_execution.work_order_execution.start_log",
			args: {
				work_order_id,
			}
		});
		return resp.message;
	}
	frappe.bnovate.work_order_execution.start_time_log = start_time_log;


	async function stop_time_log(work_order_id) {
		let resp = await frappe.call({
			method: "bnovate.bnovate.page.work_order_execution.work_order_execution.stop_log",
			args: {
				work_order_id,
			}
		});
		return resp.message;
	}
	frappe.bnovate.work_order_execution.stop_time_log = stop_time_log;


	async function fetch_item_details(item_codes) {
		// Fetch item detail docs, store in locals["Items"].
		let promises = [];
		for (let item_code of item_codes) {
			promises.push(frappe.model.with_doc("Item", item_code));
		}

		return Promise.all(promises);
	}

	// TODO: delete?
	async function create_batch_with_autonaming(item_code) {
		return await frappe.db.insert({
			doctype: "Batch",
			title: `Item ${item_code}`,
			item: item_code,
		})
	}

	async function get_or_create_batch(item_code, batch_no) {
		// Creates batch if it doesn't exist yet.
		// If no batch name is specified, let ERPNext decide it 
		// (only works for items where that option is set)
		if (!batch_no) {
			return await frappe.db.insert({
				doctype: "Batch",
				item: item_code,
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
		})
	}

	// LISTENERS
	////////////////////////////

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
		[...document.querySelectorAll('.print-wo-label')]
			.map(el => el.addEventListener('click', event => {
				window.open(
					frappe.urllib.get_full_url(
						"/api/method/bnovate.bnovate.utils.labels.download_wo_label"
						+ "?ste_name=" + encodeURIComponent(el.dataset.docname)
					),
					"_blank"
				); // _blank opens in new tab.
			}));

		[...document.querySelectorAll('.print-pouch-label')]
			.map(el => el.addEventListener('click', event => {
				window.open(
					frappe.urllib.get_full_url(
						"/api/method/bnovate.bnovate.utils.labels.download_pouch_label"
						+ "?ste_name=" + encodeURIComponent(el.dataset.docname)
					),
					"_blank"
				); // _blank opens in new tab.
			}))
	}

	function attach_additional_item_buttons() {
		const add_button = document.querySelectorAll('.add-items')[0];
		if (add_button) {
			add_button.addEventListener('click', async event => {
				await prompt_additional_item();
				draw();
			});
		}
		[...document.querySelectorAll('.remove-additional-item')]
			.map(el => el.addEventListener('click', async event => {
				await state.remove_additional_item(el.dataset.row);
				draw();
			}));

	}

	function attach_timer_buttons() {
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