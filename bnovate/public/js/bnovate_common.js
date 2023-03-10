// Set navbar to an obvious colour if running on dev machine:
if (window.location.host.indexOf("localhost") >= 0) {
  let link = document.createElement('link');
  link.type = 'text/css';
  link.rel = 'stylesheet';
  link.href = '/assets/bnovate/bnovate-dev.css';
  document.querySelector('head').appendChild(link);
}
if (parseInt(Math.random() * 100) == 42 || frappe.datetime.get_today().endsWith('04-01')) {
  console.log("Party time!")
  document.querySelector("body").classList.add('party-time');
}


/*  ***********************
 * This file contains common global functions 
 * 
 *  *********************** */

function get_label(doctype, docname, print_format, label_reference) {
  window.open(
    frappe.urllib.get_full_url(
      "/api/method/bnovate.bnovate.utils.labels.download_label_for_doc"
      + "?doctype=" + encodeURIComponent(doctype)
      + "&docname=" + encodeURIComponent(docname)
      + "&print_format=" + encodeURIComponent(print_format)
      + "&label_reference=" + encodeURIComponent(label_reference)
    ),
    "_blank"
  );
}

/***********************************
 * Client-side wrappers for IoT APIS
 ***********************************/

// Get RMS device id based on device serial number
async function rms_get_id(serial) {
  let resp = await frappe.call({
    method: "bnovate.bnovate.utils.iot_apis.rms_get_id",
    args: {
      serial
    }
  });
  return resp.message;
}

// Get info from single device from RMS id
async function rms_get_device(device_id) {
  let resp = await frappe.call({
    method: "bnovate.bnovate.utils.iot_apis.rms_get_device",
    args: {
      device_id
    }
  });
  return resp.message;
}


// Return array of connection configs with active sessions
// Optional device_id. If unspecified, returns all configs.
async function rms_get_sessions(device_id) {
  let sessions = await frappe.call({
    method: "bnovate.bnovate.utils.iot_apis.rms_get_access_sessions",
    args: {
      device_id
    }
  });
  return sessions.message;
}

// Open a new session for an existing remote configuration
async function rms_start_session(config_id, device_id) {
  let resp = await frappe.call({
    method: "bnovate.bnovate.utils.iot_apis.rms_start_session",
    args: {
      config_id
    }
  });
  const channel = resp.message;

  while (true) {
    const status = await rms_get_status(channel);
    let [last_update] = status[device_id].slice(-1);

    frappe.show_progress("Starting session....", status[device_id].length, 8, last_update ? last_update.value : null);

    if (last_update.status === "error" || last_update.status === "completed") {
      frappe.hide_progress();

      if (last_update.status === "error") {
        console.log(last_update)
        frappe.msgprint({
          title: __("Error initializing connection"),
          message: last_update.value || last_update.errorCode.toString(),
          indicator: 'red',
        })
      }

      return last_update.link
    }

    // Sleep 1 sec and loop again
    await new Promise(resolve => setTimeout(resolve, 1000))
  }
}

// Get status updates on notification channel
async function rms_get_status(channel) {
  let resp = await frappe.call({
    method: "bnovate.bnovate.utils.iot_apis.rms_get_status",
    args: {
      channel
    }
  });
  return resp.message;
}

// TMP
async function rms_initialize_device(device_id, device_name) {
  let resp = await frappe.call({
    method: "bnovate.bnovate.utils.iot_apis.rms_initialize_device",
    args: {
      device_id,
      device_name
    }
  });
  return resp.message;
}


// For fun
async function get_status(device_id, password, attempt = 1) {
  if (attempt >= 3) {
    return;
  }

  const connections = await rms_get_sessions(device_id);
  const https = connections.find(s => s.protocol == "https");

  if (!https) {
    console.log("fail");
    return;
  }

  if (!https.sessions.length) {
    await rms_start_session(https.id, device_id);
    return get_status(device_id, password, attempt + 1)
  }

  // console.log(https)
  const url = 'https://' + https.sessions[0].url + '/api/status';
  const headers = { 'Authorization': 'Basic ' + btoa('user:' + password) };
  // console.log(url, headers);
  let resp = await fetch(url, { headers });
  let status = await resp.json();
  console.log(status);
  return status;
}