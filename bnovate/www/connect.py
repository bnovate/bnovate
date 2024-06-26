# Show list of all instruments owned by that customer

import frappe

from frappe import _

from frappe.exceptions import ValidationError

from bnovate.bnovate.utils.iot_apis import (rms_get_access_configs, rms_initialize_device, _rms_get_device)
from bnovate.bnovate.utils.realtime import set_status, STATUS_RUNNING, STATUS_DONE
from bnovate.bnovate.doctype.connectivity_package.connectivity_package import _get_instrument_status
from bnovate.bnovate.doctype.audit_log import audit_log

from .helpers import get_session_customers, get_session_primary_customer, auth, build_sidebar

no_cache = 1

def get_context(context):
    auth(context)
    context.customers = sorted(get_session_customers(), key=lambda c: c.customer_name)
    context.instruments = get_instruments(context.customers)
    # build_sidebar(context)
    context.title = _("Connect BactoLink")
    context.add_breadcrumbs = True
    context.parents = [
		{ "name": _("Instruments"), "route": "/instruments" },
	]

    # Find gateway serial No in URL
    context.serial_no = frappe.form_dict.serial_no
    return context

def get_instruments(customers):
    return {c.docname: get_instruments_one_customer(c) for c in customers}

def get_instruments_one_customer(customer):
    assets = frappe.get_all("Serial No", filters={
            "owned_by": ["=", customer.docname],
            "item_group": ["=", "Instruments"],
        },
        fields="*"
    )

    for asset in assets:
        # Name stored in DB can be outdated:
        asset.owned_by_name = customer.customer_name

        # Find service agreements
        sa = frappe.get_all("Subscription Contract", filters={
                "serial_no": ["=", asset.serial_no],
                "status": ["=", "Active"]
            },
            fields="*"
        )
        if sa:
            asset.sa = sa[0]

        # Find connectivity packages
        cp = frappe.get_all("Connectivity Package", filters={
                "instrument_serial_no": ["=", asset.serial_no],
                "customer": ["=", asset.owned_by]
            },
            fields="*"
        )

        if cp:
            asset.cp = cp[0]
            if asset.cp.rms_id:
                access_configs = rms_get_access_configs(asset.cp.rms_id, auth=False)
                web = [ c for c in access_configs if 'protocol' in c and c['protocol'] == 'https' ]
                vnc = [ c for c in access_configs if 'protocol' in c and c['protocol'] == 'vnc' ]

                if web:
                    asset.cp.web = web[0]
                if vnc:
                    asset.cp.vnc = vnc[0]

    return assets

@frappe.whitelist()
def portal_initialize_device(teltonika_serial, device_name, task_id=None):
    """ Scan ports and create remote access configs. Return device details. """

    # Function is basically rewritten for more interactive feedback.

    # - Find associated Connectivity Package (CP)
    # - Authenticate: must belong to a linked Customer
    # - Get Device ID from CP
    # - Initialize using device ID.
    # - Fetch and associate instrument SN

    progress = [
        {
            "stage": "verify_gateway",
            "description": _("Verifying Gateway..."),
            "code": -1, # None: not started; -1: running; 0: no error; >0: error
        },
        {
            "stage": "detect_instrument",
            "description": _("Detecting Instrument..."),
            "code": None,
        },
        {
            "stage": "detect_sn",
            "description": _("Detecting SN..."),
            "code": None,
        },
    ]

    audit_log.log(
        action="Gateway Autoconfiguration Request",
        data={
            'teltonika_serial': teltonika_serial,
            'device_name': device_name,
        },
    )
    set_status(progress, task_id)

    cp = frappe.get_value("Connectivity Package", filters={
        "teltonika_serial": ["=", teltonika_serial],
    }, fieldname=['name', 'customer', 'rms_id'], as_dict=True)

    if cp is None:
        progress[0]["code"] = 1
        progress[0]["error"] = _("Unregistered serial number")
        set_status(progress, task_id, STATUS_DONE)
        frappe.throw("Unregistered serial number {}".format(teltonika_serial))

    if cp.customer is None or all(customer.docname != cp.customer for customer in get_session_customers()):
        # None of the linked customers match this connectivity package owner
        progress[0]["code"] = 1
        progress[0]["error"] = _("Unauthorized")
        set_status(progress, task_id, STATUS_DONE)
        frappe.throw("{} does not have access to device {}".format(frappe.session.user, teltonika_serial))

    # If this point is reached, user is authorized.

    # Check that device is online
    dev = _rms_get_device(cp.rms_id, auth=False)
    if not dev["status"]:
        progress[0]["code"] = 1
        progress[0]["error"] = _("Link is Offline")
        return set_status(progress, task_id, STATUS_DONE)

    # Start scan
    progress[0]["code"] = 0
    progress[1]["code"] = -1
    set_status(progress, task_id)

    try:
        connections = rms_initialize_device(cp.rms_id, device_name, auth=False)
        frappe.db.set_value('Connectivity Package', cp.name, 'device_name', device_name)
    except Exception as e:
        progress[1]["code"] = 1
        progress[1]["error"] = str(e)
        return set_status(progress, task_id, STATUS_DONE)

    progress[1]["code"] = 0
    progress[2]["code"] = -1
    set_status(progress, task_id)

    # Check that HTTPS is available
    if not next((c for c in connections if c['protocol']), False):
        progress[2]["code"] = 1
        progress[2]["error"] = _("HTTPS not available")
        return set_status(progress, task_id, STATUS_DONE)

    # Get SN
    try:
        instrument_status = _get_instrument_status(cp.name, auth=False)
    except Exception as e:
        progress[2]["code"] = 1
        progress[2]["error"] = str(e)
        set_status(progress, task_id, STATUS_DONE)
        raise e

    if 'serialNumber' not in instrument_status:
        progress[2]["code"] = 1
        progress[2]["error"] = _("No serial number found")
        set_status(progress, task_id, STATUS_DONE)
        frappe.throw(_("No serial number found"))

    sn = instrument_status['serialNumber']

    # Check serial number exists in our DB
    try:
        frappe.get_doc("Serial No", sn)
    except frappe.DoesNotExistError:
        progress[2]["code"] = 1
        progress[2]["error"] = _("Serial No does not match a known instrument")
        set_status(progress, task_id, STATUS_DONE)
        frappe.throw("Serial No {} does not match a known instrument".format(sn))
    except Exception as e:
        progress[2]["code"] = 1
        set_status(progress, task_id, STATUS_DONE)
        raise e

    frappe.db.set_value('Connectivity Package', cp.name, 'instrument_serial_no', sn)
    progress[2]["code"] = 0
    set_status(progress, task_id, STATUS_DONE)

    audit_log.log(
        action="Gateway Autoconfiguration Success",
        data={
            'teltonika_serial': teltonika_serial,
            'device_name': device_name,
        },
        serial_no=sn,
        connectivity_package=cp.name,
    )

    return _rms_get_device(cp.rms_id, auth=False)
