# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "bnovate"
app_title = "bNovate"
app_publisher = "libracore"
app_description = "ERPNext applications for bNovate"
app_icon = "octicon octicon-beaker"
app_color = "#3b6e8f"
app_email = "info@libracore.com"
app_license = "AGPL"

# Fixtures
# -----------------
# (add docs created for this app): custom roles, permissions...
# Need to run `bench export-fixtures` and add fixtures/ folder to git.
fixtures = [
    {
        "dt": "Role",
        "filters": [["role_name", "like", "IoT%"]],
    },
    {
        "dt": "Custom Field",
        "filters": [["name", "in", [
            "Customer Group-taxes_and_charges_template", # Used to invoice subscriptions
            "Sales Invoice Item-subscription",
            "Delivery Note-payment_terms_template", # Used to match invoice to SO payment terms through DN
            "Work Order-time_per_unit", # Used for time tracking from Work Order Execution page
            "Work Order-total_time",
            "Work Order-time_log",
        ]]]
    }
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = [
    "/assets/css/bnovate.min.css",
]
app_include_js = [ # Note to self: in case of changes, may need to run bench build --app bnovate
    "/assets/bnovate/js/bnovate_common.js",
    "/assets/js/bnovate_libs.min.js",
    # "/assets/js/bnovate.js",   # Empty probably because it wasn't coded as a module.
]

# include js, css files in header of web template
# web_include_css = "/assets/bnovate/css/bnovate.css"
# web_include_js = "/assets/bnovate/js/bnovate.js"

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Item" : ["public/js/item.js"],
    "Customer" : ["public/js/customer.js"],
    "Quotation" : ["public/js/quotation.js"],
    "Sales Order" : ["public/js/sales_order.js"],
    "Delivery Note" : ["public/js/delivery_note.js"],
    "Sales Invoice" : ["public/js/sales_invoice.js"],
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "bnovate.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "bnovate.install.before_install"
# after_install = "bnovate.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "bnovate.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
#	}
    "Work Order": {
        "before_save": "bnovate.bnovate.page.work_order_execution.work_order_execution.calculate_total_time",
        "on_update_after_submit": "bnovate.bnovate.page.work_order_execution.work_order_execution.calculate_total_time",
    },
    "Stock Entry": {
        "on_submit": "bnovate.bnovate.page.work_order_execution.work_order_execution.update_work_order_unit_time",
        "on_cancel": "bnovate.bnovate.page.work_order_execution.work_order_execution.update_work_order_unit_time",
    }
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"bnovate.tasks.all"
# 	],
# 	"daily": [
# 		"bnovate.tasks.daily"
# 	],
# 	"hourly": [
# 		"bnovate.tasks.hourly"
# 	],
# 	"weekly": [
# 		"bnovate.tasks.weekly"
# 	]
# 	"monthly": [
# 		"bnovate.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "bnovate.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "bnovate.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "bnovate.task.get_dashboard_data"
# }

