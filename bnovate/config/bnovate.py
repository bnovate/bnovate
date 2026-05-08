from __future__ import unicode_literals
from frappe import _


def get_data():
    return [
        {
            "label": _("Order Tracking"),
            "icon": "octicon octicon-git-compare",
            "items": [
                {
                    "type": "doctype",
                    "name": "Refill Request",
                    "label": _("Refill Request"),
                    "description": _("Customers requesting refills through Portal")
                },
                {
                    "type": "report",
                    "name": "Orders to Fulfill",
                    "label": _("Orders to Fulfill"),
                    "doctype": "Sales Order",
                    "is_query_report": True
                },
                {
                    "type": "report",
                    "name": "Order Book",
                    "label": _("Order Book"),
                    "doctype": "Sales Order",
                    "is_query_report": True
                },
                {
                    "type": "doctype",
                    "name": "Subscription Contract",
                    "label": _("Subscription Contract"),
                    "description": _("Subscriptions and service contracts")
                },
                {
                    "type": "report",
                    "name": "Breakbulk Data Export",
                    "label": _("Breakbulk Data Export"),
                    "doctype": "Sales Order",
                    "is_query_report": True
                },
            ]
        },
        {
            "label": _("Cartridge Tools"),
            "icon": "octicon octicon-git-compare",
            "items": [
                {
                    "type": "doctype",
                    "name": "Storage Location",
                    "label": _("Storage Location"),
                    "description": _("Storage Locations")
                },
                {
                    "type": "report",
                    "name": "Enclosure Movement History",
                    "label": _("Enclosure Movement History"),
                    "doctype": "Serial No",
                    "is_query_report": True
                },
                {
                    "type": "report",
                    "name": "Enclosure Filling History",
                    "label": _("Enclosure Filling History"),
                    "doctype": "Serial No",
                    "is_query_report": True
                },
                {
                    "type": "report",
                    "name": "Shipping And Billing History",
                    "label": _("Shipping And Billing History"),
                    "doctype": "Serial No",
                    "is_query_report": True
                },
                {
                    "type": "report",
                    "name": "Cartridge Status",
                    "label": _("Cartridge Status"),
                    "doctype": "Serial No",
                    "is_query_report": True
                },
                {
                    "type": "page",
                    "name": "cartridge-return",
                    "label": _("Cartridge Return"),
                    "description": _("Confirm return of cartridges")
                }
            ]
        },
        {
            "label": _("Production"),
            "icon": "octicon octicon-git-compare",
            "items": [
                {
                    "type": "report",
                    "name": "Open Work Orders for Lab",
                    "label": _("Open Work Orders for Lab"),
                    "doctype": "Work Order",
                    "is_query_report": True,
                },
                {
                    "type": "report",
                    "name": "Work Order Planning",
                    "label": _("Work Order Planning"),
                    "doctype": "Work Order",
                    "is_query_report": True,
                },
                {
                    "type": "page",
                    "name": "work-order-execution",
                    "label": _("Work Order Execution"),
                    "description": _("Execution page for work orders")
                },
                {
                    "type": "report",
                    "name": "BOM Search (bN)",
                    "label": _("BOM Search (bN)"),
                    "doctype": "BOM",
                    "is_query_report": True,
                },
                {
                    "type": "report",
                    "name": "BOM Stock Report (bN)",
                    "label": _("BOM Stock Report (bN)"),
                    "doctype": "BOM",
                    "is_query_report": True,
                },
                {
                    "type": "report",
                    "name": "Batch Report",
                    "label": _("Batch Report"),
                    "doctype": "Batch",
                    "is_query_report": True,
                }
            ]
        },
        {
            "label": _("Supply Tracking"),
            "icon": "octicon octicon-git-compare",
            "items": [
                {
                    "type": "report",
                    "name": "Projected Stock",
                    "label": _("Projected Stock"),
                    "doctype": "Item",
                    "is_query_report": True
                },
                {
                    "type": "report",
                    "name": "Material Request Report",
                    "label": _("Material Request Report"),
                    "doctype": "Material Request",
                    "is_query_report": True,
                },
                {
                    "type": "report",
                    "name": "Late Purchases",
                    "label": _("Late Purchases"),
                    "doctype": "Purchase Order",
                    "is_query_report": True
                }
            ]
        },
        {
            "label": _("Service & Support"),
            "icon": "octicon octicon-git-compare",
            "items": [
                {
                    "type": "doctype",
                    "name": "Service Report",
                    "label": _("Service Report"),
                    "description": _("Service Report")
                },
                {
                    "type": "report",
                    "name": "Service History",
                    "label": _("Service History"),
                    "doctype": "Service Report",
                    "is_query_report": True
                }
            ]
        },
        {
            "label": _("KPIs"),
            "icon": "octicon octicon-git-compare",
            "items": [
                {
                    "type": "report",
                    "name": "Weekly Sales",
                    "label": _("Weekly Sales"),
                    "doctype": "Sales Order",
                    "is_query_report": True
                },
                {
                    "type": "report",
                    "name": "On Time Delivery KPIs",
                    "label": _("On Time Delivery KPIs"),
                    "doctype": "Sales Order",
                    "is_query_report": True
                },
                {
                    "type": "report",
                    "name": "Revenue Analytics",
                    "label": _("Revenue Analytics"),
                    "doctype": "Sales Invoice",
                    "is_query_report": True
                },
                
            ]
        },
        {
            "label": _("Accounting"),
            "icon": "octicon octicon-git-compare",
            "items": [
                {
                    "type": "page",
                    "name": "file_uploader",
                    "label": _("PINV uploader"),
                    "description": _("Bulk upload scanned purchase invoices")
                },
                {
                    "type": "report",
                    "name": "Aggregate Invoicing",
                    "label": _("Aggregate Invoicing"),
                    "doctype": "Subscription Contract",
                    "is_query_report": True
                }, {
                    "type": "report",
                    "name": "Item-wise Sales History (bN)",
                    "label": _("Item-wise Sales History (bN)"),
                    # Not actually GL entry but I only want to show to accounting ppl.
                    "doctype": "GL Entry",
                    "is_query_report": True
                }, {
                    "type": "report",
                    "name": "Item-wise Sales Register (bN)",
                    "label": _("Item-wise Sales Register (bN)"),
                    "doctype": "GL Entry",
                    "is_query_report": True
                }, {
                    "type": "report",
                    "name": "Item-wise Purchase Register (bN)",
                    "label": _("Item-wise Purchase Register (bN)"),
                    "doctype": "GL Entry",
                    "is_query_report": True
                }, {
                    "type": "report",
                    "name": "General Ledger for Export (bN)",
                    "label": _("General Ledger for Export (bN)"),
                    "doctype": "GL Entry",
                    "is_query_report": True
                }, {
                    "type": "report",
                    "name": "Accounts Receivable (bN)",
                    "label": _("Accounts Receivable (bN)"),
                    # Not actually GL entry but I only want to show to accounting ppl.
                    "doctype": "GL Entry",
                    "is_query_report": True
                }, {
                    "type": "report",
                    "name": "Accounts Payable (bN)",
                    "label": _("Accounts Payable (bN)"),
                    # Not actually GL entry but I only want to show to accounting ppl.
                    "doctype": "GL Entry",
                    "is_query_report": True
                }, {
                    "type": "report",
                    "name": "Party Ledger per Month",
                    "label": _("Party Ledger per Month"),
                    "doctype": "GL Entry",
                    "is_query_report": True
                }, {
                    "type": "report",
                    "name": "Deferred Revenue Report",
                    "label": _("Deferred Revenue Report"),
                    "doctype": "GL Entry",
                    "is_query_report": True
                }, {
                    "type": "doctype",
                    "name": "Custom Shipping Rule",
                    "label": _("Shipping Rule"),
                    "description": _("Shipping Rules for bNovate")
                }, {
                    "type": "doctype",
                    "name": "Fixed Currency Exchange",
                    "label": _("Fixed Currency Exchange"),
                    "description": _("Long-term currency exchange rates, used for shipping rates")
                }
            ]
        },
        {
            "label": _("IC Accounting"),
            "icon": "octicon octicon-git-compare",
            "items": [
                {
                    "type": "doctype",
                    "name": "IC Account Group",
                    "label": _("IC Account Group"),
                    "description": _("Definition of the IC Accounting aggregation groups")
                },
                {
                    "type": "report",
                    "name": "IC Balance Sheet",
                    "label": _("IC Balance Sheet"),
                    "doctype": "GL Entry",
                    "is_query_report": True   
                },
                {
                    "type": "report",
                    "name": "IC Profit And Loss Statement",
                    "label": _("IC Profit And Loss Statement"),
                    "doctype": "GL Entry",
                    "is_query_report": True   
                }
            ]
        },
        {
            "label": _("IoT"),
            "icon": "octicon octicon-git-compare",
            "items": [
                {
                    "type": "page",
                    "name": "device-map",
                    "label": _("Connected Device Map"),
                    "description": _("Information about connected devices")
                },
                {
                    "type": "doctype",
                    "name": "Connectivity Package",
                    "label": _("Connectivity Package"),
                    "description": _("Connectivity Package")
                }, {
                    "type": "report",
                    "name": "Connectivity Data Usage",
                    "label": _("Data Usage"),
                    "doctype": "Connectivity Package",
                    "is_query_report": True
                }, {
                    "type": "report",
                    "name": "Portal Users",
                    "label": _("Portal Users"),
                    "doctype": "Contact",
                    "is_query_report": True
                }
            ]
        },
        {
            "label": _("Switzerland"),
            "icon": "fa fa-money",
            "items": [
                {
                    "type": "page",
                    "name": "bank_wizard",
                    "label": _("Bank Wizard"),
                    "description": _("Bank Wizard")
                },
                {
                    "type": "doctype",
                    "name": "Payment Proposal",
                    "label": _("Payment Proposal"),
                    "description": _("Payment Proposal")
                },
                {
                    "type": "doctype",
                    "name": "Payment Reminder",
                    "label": _("Payment Reminder"),
                    "description": _("Payment Reminder")
                },
                {
                    "type": "doctype",
                    "name": "VAT Declaration",
                    "label": _("VAT Declaration"),
                    "description": _("VAT Declaration")
                },
                {
                    "type": "report",
                    "name": "Kontrolle MwSt",
                    "label": _("Kontrolle MwSt"),
                    "doctype": "Sales Invoice",
                    "is_query_report": True
                },
                {
                    "type": "doctype",
                    "name": "Salary Certificate",
                    "label": _("Salary Certificate"),
                    "description": _("Salary Certificate")
                },
                {
                    "type": "report",
                    "name": "Worktime Overview",
                    "label": _("Worktime Overview"),
                    "doctype": "Timesheet",
                    "is_query_report": True
                },
                {
                    "type": "doctype",
                    "name": "Label Printer",
                    "label": _("Label Printer"),
                    "description": _("Label Printer")
                },
                {
                    "type": "doctype",
                    "name": "Pincode",
                    "label": _("Pincode"),
                    "description": _("Pincode")
                },
                {
                    "type": "doctype",
                    "name": "ERPNextSwiss Settings",
                    "label": _("ERPNextSwiss Settings"),
                    "description": _("ERPNextSwiss Settings")
                },
                {
                    "type": "doctype",
                    "name": "Worktime Settings",
                    "label": _("Worktime Settings"),
                    "description": _("Worktime Settings")
                },
                {
                    "type": "doctype",
                    "name": "VAT query",
                    "label": _("VAT query"),
                    "description": _("VAT query")
                }
            ]
        }
    ]
