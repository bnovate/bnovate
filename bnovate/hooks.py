# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

from frappe import _

app_name = "bnovate"
app_title = "bNovate"
app_publisher = "libracore"
app_description = "ERPNext applications for bNovate"
app_icon = "octicon octicon-beaker"
app_color = "#3b6e8f"
app_email = "info@libracore.com"
app_license = "AGPL"
app_logo_url = "/assets/bnovate/img/bnovate_logo.svg"

# Fixtures
# -----------------
# (add docs created for this app): custom roles, permissions...
# Need to run `bench export-fixtures` and add fixtures/ folder to git.
fixtures = [
    {
        "dt": "Role",
        "filters": [["role_name", "in", [
            "IoT Manager",
            "IoT User",
            "Item User",
            "Service Manager",
            "Service Technician",
            ]]],
    },
    {
        "dt": "Custom Field",
        "filters": [["name", "in", [
            # Subscription invoicing
            "Customer Group-taxes_and_charges_template",
            "Sales Invoice Item-subscription",
            "Sales Invoice Item-sc_detail",
            # Used to match invoice to SO payment terms through DN
            "Delivery Note-payment_terms_template",

            # Time tracking and workstation assignment on work orders
            "Work Order-time_per_unit", 
            "Work Order-total_time",
            "Work Order-time_log",
            "BOM-workstation",
            "Work Order-workstation",
            "BOM-bom_description",
            "Work Order-bom_description",
            "Stock Entry-bom_item",
            "Stock Entry Detail-delta",

            # Safety symbols on WOE:
            "BOM-safety_measures",
            "BOM-esd_protection",
            "BOM-protective_gloves",
            "BOM-lab_coat",
            "BOM-column_break_31",
            "BOM-eye_protection",
            "BOM-no_windsurfing",

            # Used to track owners of enclosures
            "Serial No-ownership_details",
            "Serial No-owned_by",
            "Serial No-owned_by_name",
            "Serial No-owner_set_by",
            "Serial No-analysis_certificate",

            # Refill requests
            "Customer-portal_settings",
            "Customer-enable_cartridge_portal",
            "Customer-allow_unstored_cartridges",
            "Customer-portal_billing_address",
            "Customer-organize_return",
            "Sales Order Item-refill_request",
            "Sales Order Item-serial_nos",  # pluralized to avoid automations from selling controller
            "Sales Order-indicator_key",
            "Sales Order Item-planned_stock",
            "Sales Order-view_stored_cartridges",
            "Sales Order-date_change_origin",
            "Sales Order Item-benchmark_delivery_date",
            "Work Order-serial_no",
            "Work Order-comment",
            "Serial No-open_sales_order",
            "Serial No-open_sales_order_item",
            "Serial No-cartridge_flowchart",
            "Serial No-cartridge_status",
            "Serial No-status_details",
            "Stock Entry-from_customer",
            "Stock Entry-from_customer_name",
            "Blanket Order-currency",
            "Address-portal_hide",
            "Item-compatibility",
            "Item-stability_in_months",
            "Item-check_serial_no_on_delivery",

            # Addresses
            "Address-company_name",
            # DN workflow
            "Delivery Note-shipment",
            "Delivery Note-carrier"
            "Delivery Note-carrier_account_no"
            "Delivery Note-tracking_no"
            "Delivery Note-column_break_25",
            "Delivery Note-packing_stage",

            # Custom shipping rules
            "Sales Taxes and Charges-hide_if_zero",
            "Quotation-custom_shipping_rule",
            "Quotation-shipping_country",
            "Sales Order-custom_shipping_rule",
            "Sales Order-shipping_country",
            "Delivery Note-custom_shipping_rule",
            "Delivery Note-shipping_country",

            # Shipments (most fields are in exported customizations - shipment.json)
            # "Company-eori_number", # Now exported in company.json
            # "Company-default_address",
            "Supplier-eori_number",
            "Delivery Note-eori_number",
            "Customer-eori_number",
            "Customer-check_eori",
            "Customer-default_incoterm",
            "Quotation-incoterm",
            "Sales Order-incoterm",
            "Sales Order-skip_autoship",
            "Delivery Note-incoterm",
            "Sales Invoice-incoterm",
            "Address-contact_name",
            "Delivery Note-carrier",
            "Delivery Note-carrier_account_no",
            "Delivery Note-tracking_no",
            "Delivery Note-column_break_20",
            "Delivery Note-parcels",
            "Delivery Note-shipment_parcel",
            "Delivery Note-parcel_template",
            "Delivery Note-add_template",
            "Delivery Note-shipping_label",
            "Delivery Note-pickup_confirmation_number",
            "Delivery Note-return_tracking_no",
            "Delivery Note-return_shipping_label",
            "Delivery Note-pallets",
            "Delivery Note-pickup_comment",
            "Delivery Note-skip_autoship",
            "Delivery Note-breakbulk_master_no",
            "Shipment Parcel Template-is_pallet",
            "Shipment Parcel-is_pallet",

            # Stock management
            "Material Request Item-default_supplier",
            "Material Request Item-assigned_to",
            "Purchase Receipt-scan",
            "Stock Entry-reason",

            # Distributor Discounts
            "Customer-default_discount",
            "Quotation-default_discount",
            "Quotation-ignore_default_discount",
            "Quotation-apply_default_discount",
            "Sales Order-default_discount",
            "Sales Order-ignore_default_discount",
            "Sales Order-apply_default_discount",

            # Configuration display
            "Quotation Item-is_subitem",
            "Quotation Item-hide_price",
            "Sales Order Item-is_subitem",
            "Sales Order Item-hide_price",
            "Delivery Note Item-is_subitem",
            "Delivery Note Item-hide_price",
            "Sales Invoice Item-is_subitem",
            "Sales Invoice Item-hide_price",
            "Quotation-translate_all",
            "Quotation Item-translate",
            "Sales Order-translate_all",
            "Sales Order Item-translate",

            # Service report and instrument portal
            "Warehouse-for_user",
            "Sales Order Item-service_report",
            "Item-website_shortname",
            "Customer-portal_col_2",
            "Customer-is_service_partner",
        ]]]
    }
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = [
    "/assets/css/bnovate.min.css",
]
app_include_js = [  # Note to self: in case of changes, may need to run bench build --app bnovate
    "/assets/bnovate/js/bnovate_common.js",
    "/assets/bnovate/js/iot.js",
    "/assets/js/bnovate_libs.min.js",
    "/assets/bnovate/js/lib/jsconfetti/js-confetti.browser.js",
    # "/assets/js/bnovate.js",   # Empty probably because it wasn't coded as a module.
]

# include js, css files in header of web template
web_include_css = [
    "/assets/css/bnovate-web.min.css",
]

web_include_js = [
    "/assets/bnovate/js/bnovate_common.js",
    "/assets/bnovate/js/web_includes/helpers.js",
    "/assets/bnovate/js/lib/frappe-datatable/sortable.js",
    "/assets/bnovate/js/lib/frappe-datatable/frappe-datatable.min.js",
    "/assets/js/moment-bundle.min.js",
    "/assets/js/control.min.js",
    "/assets/js/dialog.min.js",
    "/assets/js/bnovate-web.min.js",
    "/assets/bnovate/js/lib/jsconfetti/js-confetti.browser.js",
    "/assets/bnovate/js/web_includes/login_redirect.js",
]

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Address": ["public/js/doctype_includes/address.js"],
    "Accounts Settings": ["public/js/doctype_includes/accounts_settings.js"],
    "Blanket Order": ["public/js/doctype_includes/blanket_order.js"],
    "Company": ["public/js/doctype_includes/company.js"],
    "Contact": ["public/js/doctype_includes/contact.js"],
    "Customer": ["public/js/doctype_includes/customer.js"],
    "Delivery Note": [
        "public/js/shipping.js",
        "public/js/doctype_includes/delivery_note.js",
    ],
    "Item": ["public/js/doctype_includes/item.js"],
    "Purchase Order": ["public/js/doctype_includes/purchase_order.js"],
    "Purchase Receipt": ["public/js/doctype_includes/purchase_receipt.js"],
    "Purchase Invoice": ["public/js/doctype_includes/purchase_invoice.js"],
    "Quotation": ["public/js/doctype_includes/quotation.js"],
    "Sales Order": [
        "public/js/shipping.js",
        "public/js/doctype_includes/sales_order.js",
    ],
    "Sales Invoice": ["public/js/doctype_includes/sales_invoice.js"],
    "Serial No": ["public/js/doctype_includes/serial_no.js"],
    "Stock Entry": ["public/js/doctype_includes/stock_entry.js"],
    "Work Order": ["public/js/doctype_includes/work_order.js"],
    "Material Request": ["public/js/doctype_includes/material_request.js"],
    "Shipment": ["public/js/doctype_includes/shipment.js"],
}
doctype_list_js = {
    "Item": ["public/js/doctype_includes/item_list.js"],
    "Shipment": ["public/js/doctype_includes/shipment_list.js"],
}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "index"

# website user home page (by Role)
# role_home_page = {
#     "Customer": "index"
# }

# # Website user home page, instead of directing to /me after login
website_user_home_page = ""

# Website user home page (by function)
# get_website_user_home_page = "bnovate.config.homepage.get_homepage"

has_website_permission = {
    "Service Report": "erpnext.controllers.website_list_for_contact.has_website_permission",
}

website_route_rules = [
    {
        "from_route": "/requests/<name>", 
        "to_route": "request",
        "defaults": {
            "parents": [{"label": _("Refill Requests"), "route": "requests"}]
        }
    }, {
        "from_route": "/pickup/<name>", 
        "to_route": "pickup",
    }, {
        "from_route": "/requests/<name>/pickup", 
        "to_route": "pickup",
    }, {
        "from_route": "/connect/<serial_no>", 
        "to_route": "connect",
    }, {
        "from_route": "/cartridges/<serial_no>", 
        "to_route": "cartridge",
    }, {
        "from_route": "/instruments/<serial_no>", 
        "to_route": "instrument",
    }, {
        "from_route": "/internal/storage/<key>", 
        "to_route": "internal/storage",
    }
]

standard_portal_menu_items = [
    {"title": _("Cartridges"), "route": "/cartridges", "reference_doctype": "", "role": "Customer"},
    {"title": _("Refill Requests"), "route": "/requests", "reference_doctype": "Refill Request", "role": "Customer"},
    {"title": _("Addresses"), "route": "/my_addresses", "reference_doctype": "Address", "role": "Customer"},
]

website_context = {
    "favicon": "/assets/bnovate/favicon.ico",
    # “splash_image”: “/assets/your_app/images/your_splash.png”
}

update_website_context = "bnovate.www.helpers.update_context"
extend_website_page_controller_context  = {
    "frappe.www.list": "bnovate.www.override_list",  # Translates titles...
}

website_redirects = [
    # {"source": "/redirectme(/.*)?", "target": "https://localhost:8000/\1"},
]


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
    # }
    "Work Order": {
        "before_save": [
            "bnovate.bnovate.page.work_order_execution.work_order_execution.calculate_total_time",
            "bnovate.bnovate.utils.enclosures.set_wo_serial_no",
        ],
        "on_update_after_submit": [
            "bnovate.bnovate.page.work_order_execution.work_order_execution.calculate_total_time",
            "bnovate.bnovate.utils.enclosures.set_wo_serial_no",
        ]
    },
    "Stock Entry": {
        "before_save": "bnovate.bnovate.page.work_order_execution.work_order_execution.update_work_order_status_from_ste",
        "on_submit": "bnovate.bnovate.page.work_order_execution.work_order_execution.update_work_order_unit_time",
        "on_cancel": [
            "bnovate.bnovate.page.work_order_execution.work_order_execution.update_work_order_unit_time",
            "bnovate.bnovate.page.work_order_execution.work_order_execution.update_work_order_status_from_ste",
        ],
        "after_delete": "bnovate.bnovate.page.work_order_execution.work_order_execution.update_work_order_status_from_ste",
    },
    "Purchase Order": {
        "before_submit": "bnovate.bnovate.utils.controllers.check_blanket_order_currency",
    },
    "Sales Order": {
        "before_submit": [
            "bnovate.bnovate.utils.enclosures.check_so_serial_no",
            "bnovate.bnovate.utils.controllers.check_blanket_order_currency",
        ],
        "on_submit": [
            "bnovate.bnovate.doctype.refill_request.refill_request.update_status_from_sales_order",
            "bnovate.bnovate.doctype.service_report.service_report.update_status_from_sales_order",
        ],
        "on_update_after_submit": [
            "bnovate.bnovate.utils.enclosures.check_so_serial_no",
        ],
        "before_update_after_submit": [
            "bnovate.bnovate.utils.controllers.check_delivery_date_updates",
        ],
        "on_cancel": [
            "bnovate.bnovate.doctype.refill_request.refill_request.update_status_from_sales_order",
            "bnovate.bnovate.doctype.service_report.service_report.update_status_from_sales_order",
        ],
        "on_change": "bnovate.bnovate.utils.enclosures.associate_so_serial_no",
    },
    "Delivery Note": {
        "before_save": [
            "bnovate.bnovate.utils.shipping.set_pallets",
            "bnovate.bnovate.utils.enclosures.check_serial_no_in_dn",  # TODO remove this is only for testing
        ],
        "before_submit": [
            "bnovate.bnovate.utils.enclosures.check_serial_no_in_dn",
        ],
        "on_submit": [
            "bnovate.bnovate.utils.enclosures.set_owner_from_dn",
            "bnovate.bnovate.doctype.refill_request.refill_request.update_status_from_delivery_note",
        ],
        "on_update_after_submit": [
            "bnovate.bnovate.doctype.refill_request.refill_request.update_status_from_delivery_note",
        ],
        "on_cancel": [
            "bnovate.bnovate.utils.enclosures.set_owner_from_dn",
            "bnovate.bnovate.doctype.refill_request.refill_request.update_status_from_delivery_note",
        ],
    },
    "Shipment": {
        "before_save": [
            "bnovate.bnovate.utils.shipping.set_pallets",
            "bnovate.bnovate.utils.shipping.set_totals",
            "bnovate.bnovate.utils.shipping.set_missing_values",
        ],
        "on_submit": [
            "bnovate.bnovate.utils.shipping.set_totals",
            "bnovate.bnovate.utils.shipping.set_missing_values",
        ]
    }
}

# Scheduled Tasks
# ---------------

scheduler_events = {
    # 	"all": [
    # 		"bnovate.tasks.all"
    # 	],
    "daily": [
        "bnovate.bnovate.doctype.subscription_contract.subscription_contract.update_subscription_status",
        "bnovate.bnovate.utils.shipping.update_tracking_undelivered",
    ],
    # 	"hourly": [
    # 		"bnovate.tasks.hourly"
    # 	],
    # 	"weekly": [
    # 		"bnovate.tasks.weekly"
    # 	]
    	"monthly": [
            "bnovate.bnovate.doctype.connectivity_usage.connectivity_usage.fetch_usage_last_few_months",
    	]
}

# Testing
# -------

# before_tests = "bnovate.install.before_tests"

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
	# "erpnext.stock.get_item_details.get_item_details": "bnovate.bnovate.utils.overrides.get_item_details",
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
override_doctype_dashboards = {
    "Serial No": "bnovate.bnovate.utils.dashboards.get_serial_no_dashboard_data",
    "Sales Order": "bnovate.bnovate.utils.dashboards.get_sales_order_dashboard_data",
}

# Jinja
# ----------------------------

jenv = {
    "methods": [
        "find_serial_no:bnovate.bnovate.doctype.storage_location.storage_location.find_serial_no",
        "find_serial_nos:bnovate.bnovate.doctype.storage_location.storage_location.find_serial_nos",
        "is_enclosure:bnovate.bnovate.utils.enclosures.is_enclosure",
        "get_print:bnovate.bnovate.utils.get_print_html",
    ],
}