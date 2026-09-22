# (C) 2026, bNovate
#
# Work Order calendar view: fetches item code, item name and qty so they show
# directly on calendar events (frappe.desk.calendar.get_events only fetches
# the fields listed in field_map, which isn't enough to build a useful title).

import json

import frappe

# Hex values match frappe.ui.color_map's "extra-light" shade for each name,
# so the calendar event colors line up with the rest of the desk's indicators.
STATUS_COLORS = {
    "Completed": "#cef6d1",  # green / success
    "In Process": "#ffd2c2",  # orange / warning
}
DEFAULT_STATUS_COLOR = "#ffc4c4"  # red / danger


@frappe.whitelist()
def get_events(doctype, start, end, field_map=None, filters=None):
    if not frappe.has_permission("Work Order"):
        frappe.throw(frappe._("Not Permitted"), frappe.PermissionError)

    if filters:
        filters = json.loads(filters)
    else:
        filters = []

    start_date = "ifnull(planned_start_date, '0001-01-01 00:00:00')"
    end_date = "ifnull(planned_end_date, '2199-12-31 00:00:00')"
    filters += [
        ["Work Order", start_date, "<=", end],
        ["Work Order", end_date, ">=", start],
    ]

    rows = frappe.get_list(
        "Work Order",
        fields=[
            "name",
            "planned_start_date",
            "planned_end_date",
            "status",
            "docstatus",
            "production_item",
            "item_name",
            "qty",
            "produced_qty",
        ],
        filters=filters,
    )

    for row in rows:
        qty = ("%g" % row.qty) if row.qty else row.qty
        row["title"] = "{name} | {qty} × {item_code}: {item_name}".format(
            name=row.name, qty=qty, item_code=row.production_item, item_name=row.item_name
        )
        # Events get squeezed very narrow when several Work Orders overlap in
        # the week/day view, so the wrapped title text alone can become
        # unreadable; the native tooltip (see eventRender) covers that case.
        row["tooltip"] = "{title}".format(title=row.title, name=row.name)
        row["color"] = STATUS_COLORS.get(row.status, DEFAULT_STATUS_COLOR)

    return rows
