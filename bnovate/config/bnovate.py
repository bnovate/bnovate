from __future__ import unicode_literals
from frappe import _

def get_data():
    return[
        {
            "label": _("Order Tracking"),
            "icon": "octicon octicon-git-compare",
            "items": [
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
                   }         
            ]
        }, 
        {
            "label": _("Cartridge Tools"),
            "icon": "octicon octicon-git-compare",
            "items": [
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
                        "name": "Stored Cartridges",
                        "label": _("Stored Cartridges"),
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
                        "type": "page",
                        "name": "work-order-execution",
                        "label": _("Work Order Execution"),
                        "description": _("Execution page for work orders")            
                   }         
            ]
        },
        {
            "label": _("Production Tracking"),
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
                        "name": "Late Purchases",
                        "label": _("Late Purchases"),
                        "doctype": "Purchase Order",
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
                        "name": "Weekly KPI",
                        "label": _("Weekly KPI"),
                        "doctype": "Sales Order",
                        "is_query_report": True               
                   },
                   {
                        "type": "report",
                        "name": "On Time Delivery KPIs",
                        "label": _("On Time Delivery KPIs"),
                        "doctype": "Sales Order",
                        "is_query_report": True    
                   }                   
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
                   }                   
            ]
        },
        #  {
        #     "label": _("IoT"),
        #     "icon": "octicon octicon-git-compare",
        #     "items": [
        #            {
        #                 "type": "page",
        #                 "name": "device-map",
        #                 "label": _("Connected Device Map"),
        #                 "description": _("Information about connected devices")           
        #            }
        #     ]
        # },
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
