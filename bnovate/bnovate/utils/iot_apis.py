# -*- coding: utf-8 -*-
# Copyright (c) bNovate (Douglas Watson)
# For license information, please see license.txt
#
# Wrappers for various APIs.
# -------------------------
#
#######################################################################

import time
import frappe
import concurrent.futures

from json import JSONDecodeError
from typing import List
from datetime import date, datetime
from itertools import chain

from frappe import _
from requests import request
from requests.auth import HTTPBasicAuth

from bnovate.bnovate.utils.realtime import set_status, STATUS_DONE, STATUS_RUNNING

READ, WRITE = "read", "write"

class ApiException(Exception):
    pass

class CombaseException(Exception):
    pass

class NoEndDevicesFound(ApiException):
    """ No end devices were found during port scan. """
    pass

class ChannelNotFound(ApiException):
    """ Raised when a status channel isn't found - may be too early, try again """

class TimeoutError(ApiException):
    """ Failed to complete task in the allowed time. """

class HTTPSUnavailable(ApiException):
    """ Targetted instrument does not have HTTPS service available """

class AddDeviceError(ApiException):
    """ Could not start a remote connection session """

class StartSessionError(ApiException):
    """ Could not start a remote connection session """

#######################
# HELPERS
#######################

def _auth(ptype=READ):
    return frappe.has_permission("Connectivity Package", ptype, throw=True)

def _get_settings():
    return frappe.get_single("bNovate Settings")

#######################
# BASE API CONNECTIONS
#######################

def _rms_get_status(channel, settings=None, auth=True):
    """ Return status updates on given channel, 
    
    Use in situations where authentication should be checked separately  
    """
    if auth:
        _auth(READ)
    if settings is None:
        settings = _get_settings()

    resp = request(
        "GET", 
        "https://rms.teltonika-networks.com/status/channel/" + channel,
        headers={"Authorization": "Bearer {}".format(settings.rms_api_token)}
    )

    if resp.status_code != 200:

        detail = resp.text
        try:
            detail = resp.json()
            if detail['code'] == 'CHANNEL_NOT_FOUND':
                raise ChannelNotFound("Channel doesn't exist or expired:", channel)
        except JSONDecodeError:
            pass
        raise ApiException("Error fetching RMS Status: " + str(detail))
    return resp.json()['data']

@frappe.whitelist()
def rms_get_status(channel):
    """ Return status updates on given channel, can be called from Desk  """
    # Response and error handling are slightly different from regular API
    return _rms_get_status(channel, auth=True)

def rms_monitor_status(channel, device_id, attempt=0, auth=True):
    """ Monitor status channel until completion or error """
    if attempt >= 30:
        raise ApiException("Timeout requesting status update from channel{}".format(channel))
    try:
        resp = _rms_get_status(channel, auth=auth)
    except ChannelNotFound:
        time.sleep(1)
        return rms_monitor_status(channel, device_id, attempt + 1, auth)

    if device_id not in resp:
        raise ApiException("No status update for device {} in channel {}".format(device_id, channel))

    updates = resp[device_id]

    if updates and updates[-1]['status'] in ("error", "completed"):
        if updates[-1]['status'] == "error":
            raise ApiException(updates[-1]['value'])
        return updates[-1]

    time.sleep(0.5)
    return rms_monitor_status(channel, device_id, attempt + 1, auth)


def rms_request(path, method='GET', params=None, body=None, settings=None, auth=True):
    """ Skip auth when running parallel requests, just make sure to check at least once! """
    if auth:
        _auth(READ if method == 'GET' else WRITE)
    if settings is None:
        settings = _get_settings()
    resp = request(
        method, 
        "https://rms.teltonika-networks.com" + path,
        params=params,
        json=body,
        headers={"Authorization": "Bearer {}".format(settings.rms_api_token)}
    ).json()
    if not resp['success']:
        raise ApiException("Error fetching from RMS API: " + str(resp['errors']))
    if 'data' not in resp and 'meta' in resp:
        return resp['meta']
    elif 'data' in resp:
        return resp['data']

def combase_request(path, params=None, settings=None, auth=True):
    """ Fetch path from API

    Skip permission check and settings lookup if these are called concurrently. Just make sure to 
    check at least once calling _auth()!
    
    """
    if auth:
        _auth()
    if settings is None:
        settings = _get_settings()

    resp = request(
        "GET", 
        "https://restapi2.jasper.com/rws/api/v1" + path, 
        params=params,
        auth=HTTPBasicAuth(settings.combase_api_username, settings.combase_api_key)
    ).json()

    if 'errorCode' in resp:
        raise CombaseException("{}: {}".format(resp['errorCode'], resp['errorMessage']))

    return resp


##################################
# WRAPPERS
##################################

@frappe.whitelist()
def rms_get_device(device_id):
    return _rms_get_device(device_id)

def _rms_get_device(device_id, auth=True):
    """ Return info from single device """
    return rms_request("/api/devices/{id}".format(id=device_id), auth=auth)


def rms_set_device(device_id, payload, auth=True):
    """ Set device data """
    return rms_request("/api/devices/{}".format(device_id),
    "PUT",
    body=payload,
    auth=auth)


def rms_get_devices(settings=None):
    """ Return list of all devices connected to RMS """
    return rms_request("/api/devices", params={"limit": 10000}, settings=settings)

def rms_add_device(serial, current_admin_password, imei=None, mac=None, device_series="trb", auth=True, task_id=None):
    """ Add a device to this company's RMS account.

    TRB series need an IMEI instead of MAC.
     
    """

    settings = _get_settings()
    company_id = settings.rms_company_id

    payload = {"data": [{
        "company_id": company_id,
        "device_series": device_series,
        "serial": serial,
        "name": serial,
        "mac": mac or "",
        "imei": imei or "",
        "password_confirmation": current_admin_password,
        "auto_credit_enable": 1,
    }]}

    set_status({
        "progress": 0,
        "message": _("Initiating request..."),
    }, task_id)

    try:
        resp = rms_request(
            "/api/devices",
            "POST",
            body=payload,
            settings=settings,
            auth=auth,
        )
    except ApiException as e:
        set_status({ "progress": 0, "message": _("Error") }, task_id, STATUS_DONE)
        raise e
    channel = resp['channel']


    def wait_for_result(attempt=0, progress=0):
        time.sleep(0.5)  # Sleep first to allow channel time to appear

        if attempt > 120:
            raise TimeoutError("Timeout adding device to RMS")

        status = _rms_get_status(channel, settings=settings, auth=auth)
        if company_id not in status:
            frappe.throw("Status not available")

        last_update = status[company_id][-1]
        message = last_update['value'] if 'value' in last_update else str(last_update['errorCode']) if 'errorCode' in last_update else ''
        finished = last_update['status'] in ('error', 'warning', 'completed')
        progress = 100 * last_update['progress']['value'] / float(last_update['progress']['total']) if 'progress' in last_update else progress

        set_status({
            "progress": 100. if finished else progress,
            "message": message,
        }, task_id, STATUS_DONE if finished else STATUS_RUNNING)

        if last_update['status'] in ('error', 'warning'):
            frappe.throw(message, AddDeviceError)

        if last_update['status'] == 'completed':
            return 'success'

        return wait_for_result(attempt + 1, progress)

    return wait_for_result()


def rms_set_password(device_id, new_password, auth=True, task_id=None):
    """ Set admin password of a device """

    settings = _get_settings()
    payload = {"data": [{
        "id": device_id,
        "password": new_password,
        "password_confirmation": new_password,
    }]}

    set_status({
        "progress": 0,
        "message": _("Initiating request..."),
    }, task_id)

    try:
        resp = rms_request(
            "/api/devices/passwords/set",
            "POST",
            body=payload,
            auth=auth)
    except ApiException as e:
        set_status({ "progress": 100, "message": _("Error") }, task_id, STATUS_DONE)
        raise e
    channel = resp['channel']

    def wait_for_result(attempt=0):
        time.sleep(0.5)  # Sleep first to allow channel time to appear

        if attempt > 120:
            set_status({
                "progress": 100,
                "message": "Timeout.",
            }, task_id, STATUS_DONE)
            raise TimeoutError("Timeout adding device to RMS")

        status = _rms_get_status(channel, settings=settings, auth=auth)
        if device_id not in status:
            frappe.throw("Status not available")

        last_update = status[device_id][-1]
        message = last_update['value'] if 'value' in last_update else str(last_update['errorCode']) if 'errorCode' in last_update else ''
        finished = last_update['status'] in ('error', 'warning', 'completed')

        set_status({
            "progress": 100. if finished else 30 + attempt,
            "message": message,
        }, task_id, STATUS_DONE if finished else STATUS_RUNNING)

        if last_update['status'] in ('error', 'warning'):
            frappe.throw(message, AddDeviceError)

        if last_update['status'] == 'completed':
            return 'success'

        return wait_for_result(attempt + 1)

    return wait_for_result()
 


@frappe.whitelist()
def rms_get_id(serial):
    matches = [d for d in rms_get_devices() if d['serial'] == serial]
    if matches:
        return matches[0]['id']
    return None

def rms_port_scan(device_id, auth=True):
    """ Return available IPs and ports, i.e. instruments connected to device 

    Example return value:

    [{
            "ip": "192.168.2.148",
            "mac": "...",
            "port": [ 22, 80, 443, 5900 ],
            "vendor": "..."
    }],

    """
    meta = rms_request(
        "/api/devices/{}/port-scan".format(device_id),
        params={"type": "ethernet"},
        auth=auth
    )
    ports_info = rms_monitor_status(meta['channel'], device_id, auth=auth)
    if not 'ports' in ports_info \
            or not ports_info['ports'] \
            or not 'devices' in ports_info['ports'][0] \
            or not ports_info['ports'][0]['devices']:
        raise NoEndDevicesFound("No end devices found")
    
    return ports_info['ports'][0]['devices'][0]


def rms_create_access(device_id, payload, auth=True):
    """ Create remote access configurations. See API reference for payload format. """
    meta = rms_request(
        "/api/devices/remote-access",
        "POST",
        body=payload,
        auth=auth
    )
    return rms_monitor_status(meta['channel'], device_id, auth=auth)


def rms_delete_access(device_id, config_ids, auth=True):
    """ Delete access configurations based on IDs.

    config_ids: array of int
    """
    # Mistake in RMS API: it doesn't loop IDs. Need to do it ourselves:
    for id in config_ids:
        meta = rms_request(
            "/api/devices/remote-access",
            "DELETE",
            body={'id': [id]},
            auth=auth
        )
        rms_monitor_status(meta['channel'], device_id, auth=auth)



def rms_initialize_device(device_id, device_name, auth=True):
    """ Create remote configurations for a device. """

    # 0) Rename device and clear up existing access configs
    # 1) Port scan
    # 2) Create HTTPS and VNC remotes for first available end-device

    # Rename
    rms_set_device(device_id, {
        "name": device_name,
    }, auth)

    # Delete existing remote configs (if no end devices are available, we shouldn't display outdated configs)
    configs = rms_get_access_configs(device_id, auth=auth)
    if  configs:
        rms_delete_access(device_id, 
            [c['id'] for c in configs if c['protocol'] in ("https", "vnc")],
            auth=auth)
        
    # Port Scan
    try:
        end_device = rms_port_scan(device_id, auth)
    except NoEndDevicesFound:
        frappe.throw("No instruments connected to this Link.")

    ip, ports = end_device['ip'], end_device['port']
    data = []
    if 443 in ports:
        data.append({
            "device_id": device_id,
            "name": "{} Web Interface".format(device_name),
            "destination_ip": ip,
            "destination_port": 443,
            "protocol": "https",
            "credentials_required": False,
        })

    if 5900 in ports:
        data.append({
            "device_id": device_id,
            "name": "{} Remote Desktop".format(device_name),
            "destination_ip": ip,
            "destination_port": 5900,
            "protocol": "vnc",
            "credentials_required": False,
        })

    # Set new configs, if available
    if data:
        rms_create_access(device_id, {"data": data}, auth)

    return data

def rms_get_access_configs(device_id=None, settings=None, auth=True):
    """ Return list of access configs based on RMS ID (not SN). """
    params = None
    if device_id:
        params = {'device_id': device_id}
    configs = rms_request(
        "/api/devices/remote-access", 
        params=params,
        settings=settings,
        auth=auth,
    )
    return [c for c in configs if c['protocol']]

def rms_get_access_sessions_for_config(config, settings=None, auth=True):
    """ Return active access session urls for a given access config """
    sessions = rms_request(
        "/api/devices/connect/{config_id}/sessions".format(config_id=config['id']),
        settings=settings,
        auth=auth,
    )

    active = [s for s in sessions if int(float(s['end_time'])) > time.time()]
    active.sort(key=lambda el: int(float(el['end_time'])), reverse=True)
    return dict(sessions=active, **config)

@frappe.whitelist()
def rms_get_access_sessions(device_id=None):
    return _rms_get_access_sessions(device_id)

def _rms_get_access_sessions(device_id=None, settings=None, auth=True):
    """ Return list of access config dicts, each with its list of active sessions """
    if auth:
        _auth(WRITE)  # require write permissions since this returns active session links
    if settings is None:
        settings = _get_settings()
    configs = rms_get_access_configs(device_id, settings=settings, auth=auth)
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [ executor.submit(rms_get_access_sessions_for_config, c, settings=settings, auth=False) for c in configs ]
        responses = [ future.result() for future in concurrent.futures.as_completed(futures) ]

    # Alphabetical sort by protocol, so that they always appear in the same order.
    responses.sort(key=lambda el: el['protocol'])
    return responses


@frappe.whitelist()
def rms_start_session(config_id, device_id, duration=30*60, task_id=None):
    """ Opens a new session for an existing remote configuration. 

    Auth handled for Desk users
    """
    return _rms_start_session(config_id, device_id, duration, task_id=task_id)


def _rms_start_session(config_id, device_id, duration=30*60, settings=None, auth=True, task_id=None):
    """ Opens a new session for an existing remote configuration. Return URL.

    Auth can be checked separately for portal users.
    Pass task_id for realtime upates.
    """
    device_id = str(device_id)
    set_status({
        "progress": 5,
        "message": _("Connecting..."),
    }, task_id)

    resp = rms_request(
        "/api/devices/connect/{config_id}".format(config_id=config_id),
        "POST",
        body={"duration": duration},
        settings=settings,
        auth=auth
    )
    channel = resp['channel']

    # Re-writing the "monitor_status" code here in order to give more feedback to front-end
    def wait_for_link(attempt=0):

        if attempt > 120:
            raise TimeoutError("Timeout opening remote connection session")

        try:
            status = _rms_get_status(channel, settings=settings, auth=auth)
        except ChannelNotFound:
            time.sleep(0.5)  # Allow channel time to appear
            return wait_for_link(attempt+1)

        if device_id not in status:
            # TODO: what do we do?
            frappe.throw("Status not available")

        last_update = status[device_id][-1]
        message = last_update['value'] if 'value' in last_update else str(last_update['errorCode']) if 'errorCode' in last_update else ''

        finished = last_update['status'] in ('error', 'warning', 'completed')
        set_status({
            "progress": 100. if finished else len(status[device_id]) / 8. * 100.,
            "message": message,
        }, task_id, STATUS_DONE if finished else STATUS_RUNNING)

        if last_update['status'] in ('error', 'warning'):
            frappe.throw(message, StartSessionError)

        if last_update['status'] == 'completed':
            return last_update['link']

        time.sleep(0.5)
        return wait_for_link(attempt+1)

    return wait_for_link()


#############################
# SIM & Data provider
#############################

def combase_get_ctd_usage(iccid, settings=None, auth=True):
    """ Return data usage of SIM card in MB, or None.


    Skip permission check and settings lookup if these are called concurrently. Just make sure to 
    check at least once calling _auth()!
    
    """

    resp = combase_request("/devices/{iccid}/ctdUsages".format(iccid=iccid), 
                           settings=settings, auth=auth)

    if not 'ctdDataUsage' in resp:
        return None
    return (iccid, resp['ctdDataUsage'] / 1024 / 1024)


@frappe.whitelist()
def get_devices_and_data():
    """ Return list of all devices including combase data usage in MB """

    settings = _get_settings()
    devices = rms_get_devices(settings=settings)

    # To avoid modifying memory in the parallel fetches, build dict of iccid: data_usage:
    iccids = [ device['iccid'][:19] for device in devices 
                 if 'iccid' in device and device['iccid'] is not None]


    # Get data usage for each SIM iccid:
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [ executor.submit(combase_get_ctd_usage, iccid, settings, auth=False) for iccid in iccids ]
        responses = [ future.result() for future in concurrent.futures.as_completed(futures) ]
        lookup = { k: v for k, v in responses }

    # And assign to respective devices
    for device in devices:
        device['sim_data_usage_mb'] = 0

        if 'iccid' not in device or device['iccid'] is None:
            continue

        iccid = device['iccid'][:19]
        if iccid not in lookup:
            return
        device['sim_data_usage_mb'] = lookup[iccid]

    return devices

def combase_get_devices():
    """ Return all SIM cards registered """
    devices = []
    current_year = datetime.now().year
    for year in range(2023, current_year + 1):
        resp = {
            'lastPage': False,
            'pageNumber': 0,
        }
        while 'lastPage' in resp and not resp['lastPage']:
            resp = combase_request(
                "/devices",
                params={
                    'modifiedSince': '{year}-01-01T00:00:00+00:00'.format(year=year),
                    'pageNumber': resp['pageNumber'] + 1,
                },
            )

            if not 'devices' in resp:
                continue

            devices.extend(resp['devices'])

    return devices

def combase_get_plans():
    """ Return all rate plans """
    devices = combase_get_devices()
    return sorted(list(set(d['ratePlan'] for d in devices)))

def combase_get_cycle_usage(cycles: List[date]):
    """ Return data usage for all devices in the billing cycle

    cycle: list of dates, one per month

    """

    _auth()
    settings = _get_settings()

    start_dates = [date(d.year, d.month, 1) for d in cycles]
    plans = combase_get_plans()

    def plan_cycle_usage(plan, cycle_start):
        # Return dict of { device: usage } for a plan and cycle.
        # Return dict of { cycle, }
        # Sum all zones together for now.
        cycle_formatted = cycle_start.strftime("%Y-%m-01Z")
        usage = []
        zones = []
        resp = { 
            'lastPage': False,
            'pageNumber': 0,
        }

        # Get all pages
        while 'lastPage' in resp and not resp['lastPage']:
            resp = combase_request(
                "/usages", 
                params={
                    'ratePlanName': plan,
                    'cycleStartDate': cycle_formatted,
                    'pageNumber': resp['pageNumber'] + 1,
                },
                settings=settings,
                auth=False, 
            )

            if not 'zones' in resp:
                continue
            
            zones.extend(resp['zones'])

        for zone in zones:
            if not 'devices' in zone:
                continue
            for device in zone['devices']:
                data_usage = device['usage']['dataUsage'] / 1024 / 1024
                usage.append((cycle_start, device['deviceId'], data_usage))

        return usage

    # Collect usage data for each device and cycle
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [ executor.submit(plan_cycle_usage, plan, cycle) for plan in plans for cycle in start_dates]
        responses = list(chain(*[ future.result() for future in concurrent.futures.as_completed(futures) ]))

    # Some devices switch plan mid-cycle.
    sum_usage = {
        # SIMdeviceId: usage in MB 
    }
    for cycle, device_id, usage in sorted(responses, key=lambda r: r[0]):
        if cycle not in sum_usage:
            sum_usage[cycle] = {}

        if device_id not in sum_usage[cycle]:
            sum_usage[cycle][device_id] = 0

        sum_usage[cycle][device_id] += usage

    return sum_usage


################################
# BactoSense API interface
################################

def get_instrument_status(device_id, password="", settings=None, auth=True, task_id=None):
    """ Get instrument status, for example to fetch Serial Number or service due date.

    device_id is RMS device ID. Will fetch status from first instrument available.
    task_id: for realtime updates.
    """

    # - Check for existing remote connections
    # - If none exist, create one and start again.
    # - Pick the first HTTPS session available
    # - Fetch and return status from BactoSense API

    # Get a list of configs and associated active sessions
    sessions = _rms_get_access_sessions(device_id, settings=settings, auth=auth)
    https_configs = [s for s in sessions if s['protocol'] == "https"]

    if len(https_configs) == 0:
        raise HTTPSUnavailable("Device does not have an HTTPS connection available.")

    https = https_configs[0]

    if len(https['sessions']) == 0:
        link = _rms_start_session(https['id'], device_id, settings=settings, auth=auth, task_id=task_id)
    else:
        link = https['sessions'][0]['url']
    
    try:
        return request(
            "GET", 
            "https://{}/api/status".format(link),
            auth=HTTPBasicAuth("guest", password)
        ).json()
    except ValueError:
        frappe.throw(_("Could not fetch valid status from the instrument"))
