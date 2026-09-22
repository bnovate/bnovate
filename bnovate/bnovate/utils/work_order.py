# (C) 2026, bNovate
#
# General Work Order lifecycle rules:
# - New Work Orders default to an 8am start time instead of midnight.
# - planned_end_date tracks planned_start_date: if an end date already exists
#   it shifts along with the start, keeping the same duration; otherwise it's
#   estimated from historical data. Either way it's derived here rather than
#   left to whatever a calendar drag/resize computes (see
#   bnovate.bnovate.utils.work_order_calendar for the calendar view itself).

from __future__ import unicode_literals

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import get_datetime, flt

DEFAULT_DURATION_MINUTES = 4 * 60  # half a day, used when there's no history to estimate from


def get_mean_time_per_unit(item_code):
    """ Average minutes/unit across past Work Orders for this item.

    Same historical-average calculation used by the "Work Order Planning"
    report's Time Estimate column.
    """
    result = frappe.db.sql(
        """
        SELECT AVG(time_per_unit) AS mean_time_per_unit
        FROM `tabWork Order`
        WHERE production_item = %s AND time_per_unit > 0
        """,
        (item_code,),
        as_dict=True,
    )
    return result[0].mean_time_per_unit if result else None


def format_duration(minutes):
    hours, minutes = divmod(round(minutes), 60)
    return _("{0}h {1}m").format(hours, minutes)


def stash_previous_dates(doc, method=None):
    """ Capture planned_start_date/planned_end_date as they still are in the
    DB, before this save cycle overwrites them.

    Called on before_save and before_update_after_submit via hooks.py - both
    fire before db_update(), unlike on_update_after_submit. Must run before
    any hook in this module calls db_set(), because db_set() internally
    calls Document.load_doc_before_save() again, which re-fetches from the
    DB - harmless for a before_save update (the row hasn't changed yet), but
    for on_update_after_submit the row has ALREADY been written by then, so
    that re-fetch silently clobbers get_doc_before_save() with the new
    values. Stashing our own copy on doc.flags sidesteps that entirely.
    """
    if doc.is_new():
        doc.flags.wo_previous_start = None
        doc.flags.wo_previous_end = None
    else:
        doc.flags.wo_previous_start, doc.flags.wo_previous_end = frappe.db.get_value(
            "Work Order", doc.name, ["planned_start_date", "planned_end_date"]
        )


def default_start_time(doc, method=None):
    """ Work Orders default to an 8am start instead of midnight.

    Called on before_save and on_update_after_submit via hooks.py (not just
    before_insert), so this applies both to brand new Work Orders and to
    existing ones whose start gets reset to midnight later - e.g. a calendar
    drag in month view only carries day granularity, or a bulk edit/import.
    See set_planned_end_date for why both hooks are needed, and db_set
    likewise.
    """
    if not doc.planned_start_date:
        start = get_datetime().replace(hour=8, minute=0, second=0, microsecond=0)
    else:
        start = get_datetime(doc.planned_start_date)
        if start.hour or start.minute:
            return
        start = start.replace(hour=8)

    doc.db_set("planned_start_date", start)
    frappe.msgprint(
        _("Start time was not set, defaulted to 8:00 AM."),
        alert=True,
        indicator="blue",
    )


def set_planned_end_date(doc, method=None):
    """ Keep planned_end_date in sync whenever planned_start_date changes.

    Called on before_save and on_update_after_submit via hooks.py, so this
    applies whether the start date changes on the Work Order form, via
    calendar drag/resize, or via the "Work Order Planning" report's date
    editor. planned_start_date/planned_end_date are allow_on_submit, so an
    update to an already-submitted Work Order only fires
    on_update_after_submit (not before_save) - db_set is needed there since
    the DB row is already written by the time that hook runs. See
    set_wo_serial_no in utils/enclosures.py for the same pattern.

    - If an end date already exists, the start moves and the end date is
      shifted along with it, keeping the existing duration - no estimate,
      no toast.
    - Otherwise (new Work Order, or one that never had an end date) the end
      date is estimated from historical data, with a toast explaining where
      the number came from.
    """
    if not doc.planned_start_date:
        return

    remaining_qty = flt(doc.qty) - flt(doc.produced_qty)
    if remaining_qty <= 0:
        # Nothing left to produce (e.g. Completed) - don't rewrite history.
        return

    previous_start = get_datetime(doc.flags.wo_previous_start) if doc.flags.wo_previous_start else None
    previous_end = get_datetime(doc.flags.wo_previous_end) if doc.flags.wo_previous_end else None
    new_start = get_datetime(doc.planned_start_date)

    start_changed = previous_start is None or abs((new_start - previous_start).total_seconds()) >= 60
    if not start_changed:
        return

    if previous_start and previous_end and previous_end > previous_start:
        # Already had a duration planned - keep it, just move with the start.
        # (previous_end > previous_start guards against old records where
        # end was set before start, which isn't a duration worth preserving.)
        doc.db_set("planned_end_date", new_start + (previous_end - previous_start))
        return

    duration_minutes = DEFAULT_DURATION_MINUTES
    is_estimated = False

    mean_time_per_unit = get_mean_time_per_unit(doc.production_item)
    if mean_time_per_unit:
        duration_minutes = mean_time_per_unit * remaining_qty
        is_estimated = True

    planned_end_date = new_start + timedelta(minutes=duration_minutes)
    doc.db_set("planned_end_date", planned_end_date)

    if is_estimated:
        message = _("End time was automatically set to {0}, based on an estimated duration of {1} from prior Work Orders for this item.").format(
            frappe.format(planned_end_date, {"fieldtype": "Datetime"}), format_duration(duration_minutes)
        )
    else:
        message = _("End time was automatically set to {0}, based on a default duration of {1} (no prior data for this item).").format(
            frappe.format(planned_end_date, {"fieldtype": "Datetime"}), format_duration(duration_minutes)
        )
    frappe.msgprint(message, alert=True, indicator="blue")
