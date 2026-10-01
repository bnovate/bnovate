/* Customisations for the Work Order calendar view
 *
 * Included via hooks.py `doctype_calendar_js`, after ERPNext's own
 * work_order_calendar.js, so this fully replaces frappe.views.calendar["Work Order"].
 *
 * ERPNext's default only shows the Work Order name on each event. We fetch
 * item code, item name and qty server-side (bnovate.bnovate.utils.work_order_calendar.get_events)
 * and fold them into the title, since frappe.desk.calendar.get_events only
 * ever fetches the fields already listed in field_map.
 */

frappe.views.calendar["Work Order"] = {
	field_map: {
		"start": "planned_start_date",
		"end": "planned_end_date",
		"id": "name",
		"title": "title",
		"allDay": "allDay",
		"color": "color",
		"progress": function (data) {
			return flt(data.produced_qty) / data.qty * 100;
		}
	},
	gantt: true,
	filters: [
		{
			"fieldtype": "Link",
			"fieldname": "sales_order",
			"options": "Sales Order",
			"label": __("Sales Order")
		},
		{
			"fieldtype": "Link",
			"fieldname": "production_item",
			"options": "Item",
			"label": __("Production Item")
		},
		{
			"fieldtype": "Link",
			"fieldname": "workstation",
			"options": "Workstation",
			"label": __("Workstation")
		}

	],
	get_events_method: "bnovate.bnovate.utils.work_order_calendar.get_events",

	// Monkey-patch: enable editing of submitted docs if user has permission, since dates remain editable after submit.
	prepare_events: function (events) {
		let prepared = frappe.views.Calendar.prototype.prepare_events.call(this, events);
		prepared.forEach(d => {
			if (frappe.model.can_write(d.doctype || this.doctype)) {
				d.editable = true;
			}
		});
		return prepared;
	},
}