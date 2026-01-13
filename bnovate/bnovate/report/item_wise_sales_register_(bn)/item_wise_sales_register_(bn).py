# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe, erpnext
from frappe import _
from frappe.utils import flt
from frappe.model.meta import get_field_precision
from frappe.utils.xlsxutils import handle_html
from erpnext.accounts.report.sales_register.sales_register import get_mode_of_payments

def execute(filters=None):
    if not filters: filters = {}
    columns = get_columns()


    item_list = get_items(filters)
    return columns, item_list


def get_columns():

    cogs_info = """
    <p><b>COGS Calculation</b></p>

    <p>Fetches SUM(stock value delta) from stock ledger.</p>

    <p>Each SINV line item is related to a DN line item, which in turn is related to 
    one or more stock ledger entries (bundles can include multiple stock items). Stock ledger 
    lists stock value difference.</p>

    """

    columns = [
        {
            "fieldname": "item_group",
            "label": _("Item Group"),
            "fieldtype": "Link",
            "width": 100,
            "options": "Item Group"
        },
        {
            "fieldname": "revenue_stream",
            "label": _("Revenue Stream"),
            "fieldtype": "Data",
            "width": 100,
        },
        {
            "fieldname": "item_code",
            "label": _("Item Code"),
            "fieldtype": "Link",
            "width": 120,
            "options": "Item"
        },
        {
            "fieldname": "item_name",
            "label": _("Item Name"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "description",
            "label": "Description",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "invoice",
            "label": _("Invoice"),
            "fieldtype": "Link",
            "width": 120,
            "options": "Sales Invoice"
        },
        {
            "fieldname": "posting_date",
            "label": _("Posting Date"),
            "fieldtype": "Date",
            "width": 80
        },
        {
            "fieldname": "customer",
            "label": _("Customer"),
            "fieldtype": "Link",
            "width": 120,
            "options": "Customer"
        },
        {
            "fieldname": "customer_name",
            "label": _("Customer Name"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "customer_group",
            "label": _("Customer Group"),
            "fieldtype": "Link",
            "width": 120,
            "options": "Customer Group"
        },
        {
            "fieldname": "territory",
            "label": _("Territory"),
            "fieldtype": "Link",
            "width": 80,
            "options": "Territory"
        },
        {
            "fieldname": "territory_parent",
            "label": _("Territory Parent"),
            "fieldtype": "Link",
            "width": 80,
            "options": "Territory"
        },
        # {
        #     "fieldname": "project",
        #     "label": _("Project"),
        #     "fieldtype": "Link",
        #     "width": 80,
        #     "options": "Project"
        # },
        {
            "fieldname": "company",
            "label": _("Company"),
            "fieldtype": "Link",
            "width": 100,
            "options": "Company"
        },
        {
            "fieldname": "sales_order",
            "label": _("Sales Order"),
            "fieldtype": "Link",
            "width": 100,
            "options": "Sales Order"
        },
        {
            "fieldname": "delivery_note",
            "label": _("Delivery Note"),
            "fieldtype": "Link",
            "width": 100,
            "options": "Delivery Note"
        },
        {
            "fieldname": "so_date",
            "label": _("SO Date"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "dn_date",
            "label": _("DN Date"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "income_account",
            "label": _("Income Account"),
            "fieldtype": "Link",
            "width": 140,
            "options": "Account"
        },
        {
            "fieldname": "expense_account",
            "label": _("Expense Account"),
            "fieldtype": "Link",
            "width": 140,
            "options": "Account"
        },
        {
            "fieldname": "cost_center",
            "label": _("Cost Center"),
            "fieldtype": "Link",
            "width": 140,
            "options": "Cost Center"
        },
        {
            "fieldname": "stock_qty",
            "label": _("Stock Qty"),
            "fieldtype": "Float",
            "width": 120
        },
        {
            "fieldname": "stock_uom",
            "label": _("Stock UOM"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "currency",
            "label": _("Doc Currency"),
            "fieldtype": "Link",
            "options": "Currency",
            "width": 100
        },
        {
            "fieldname": "price_list_rate",
            "label": _("Price List Rate"),
            "fieldtype": "Currency",
            "width": 120,
            "options": "currency"
        },
        {
            "fieldname": "customer_default_discount",
            "label": _("Default Discount Percentage"),
            "fieldtype": "Percent",
            "width": 120,
        },
        {
            "fieldname": "discount_percentage",
            "label": _("Discount Percentage"),
            "fieldtype": "Percent",
            "width": 120,
        },
        {
            "fieldname": "net_rate",
            "label": _("Net Rate"),
            "fieldtype": "Currency",
            "width": 120,
            "options": "currency"
        },
        {
            "fieldname": "net_amount",
            "label": _("Net Amount"),
            "fieldtype": "Currency",
            "width": 120,
            "options": "currency"
        },
        {
            "fieldname": "company_currency",
            "label": _("Company Currency"),
            "fieldtype": "Link",
            "options": "Currency",
            "width": 100
        },
        {
            "fieldname": "base_price_list_rate",
            "label": _("Price List Rate in Company Currency"),
            "fieldtype": "Currency",
            "width": 120,
            "options": "company_currency"
        },
        {
            "fieldname": "base_net_rate",
            "label": _("Net Rate in Company Currency"),
            "fieldtype": "Currency",
            "width": 120,
            "options": "company_currency"
        },
        {
            "fieldname": "base_net_amount",
            "label": _("Net Amount in Company Currency"),
            "fieldtype": "Currency",
            "width": 120,
            "options": "company_currency"
        },
        {
            "fieldname": "cogs",
            "label": _("COGS"),
            "label": '<span data-html="true" data-toggle="tooltip" data-placement="bottom" data-container="body" title="{}">COGS <i class="fa fa-info-circle"></i></span>'.format(cogs_info), 
            "fieldtype": "Currency",
            "width": 120,
            "options": "company_currency"
        },
        {
            "fieldname": "service_report",
            "label": _("Service Report"),
            "fieldtype": "Link",
            "width": 120,
            "options": "Service Report"
        },
        {
            "fieldname": "billing_basis",
            "label": _("Billing Basis"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "enable_deferred_revenue",
            "label": _("Deferred Revenue"),
            "fieldtype": "Check",
            "width": 120
        }

    ]

    return columns

def get_conditions(filters):
    conditions = ""

    for opts in (("company", " and si.company=%(company)s"),
        ("customer", " and si.customer = %(customer)s"),
        ("item_code", " and si.item_code = %(item_code)s"),
        ("from_date", " and si.posting_date>=%(from_date)s"),
        ("to_date", " and si.posting_date<=%(to_date)s"),
        ("company_gstin", " and si.company_gstin = %(company_gstin)s"),
        ("invoice_type", " and si.invoice_type = %(invoice_type)s")):
            if filters.get(opts[0]):
                conditions += opts[1]

    if filters.get("mode_of_payment"):
        conditions += """ and exists(select name from `tabSales Invoice Payment`
            where parent=si.name
                and ifnull(`tabSales Invoice Payment`.mode_of_payment, '') = %(mode_of_payment)s)"""

    if filters.get("warehouse"):
        conditions +=  """ and exists(select name from `tabSales Invoice Item`
             where parent=si.name
                 and ifnull(`tabSales Invoice Item`.warehouse, '') = %(warehouse)s)"""


    if filters.get("brand"):
        conditions +=  """ and exists(select name from `tabSales Invoice Item`
             where parent=si.name
                 and ifnull(`tabSales Invoice Item`.brand, '') = %(brand)s)"""

    if filters.get("item_group"):
        conditions +=  """ and exists(select name from `tabSales Invoice Item`
             where parent=si.name
                 and ifnull(`tabSales Invoice Item`.item_group, '') = %(item_group)s)"""


    return conditions

def get_items(filters):
    conditions = get_conditions(filters)
    match_conditions = frappe.build_match_conditions("Sales Invoice")

    if match_conditions:
        match_conditions = " and {0} ".format(match_conditions)

    return frappe.db.sql("""
        WITH 
        cogs_per_sii AS (
            -- One row SINV items = One row of DN items
            -- One row of DN can have multiple rows in stock ledger: multiple packed items, or item leaving stock and entering customer locations
            SELECT
                sii.name as sii_name,
                SUM(sle.stock_value_difference) as cogs
                
            FROM `tabSales Invoice Item` sii
            JOIN `tabStock Ledger Entry` sle ON sle.voucher_detail_no = sii.dn_detail  
            GROUP BY sii.name
        ),
        
        sinv AS ( -- Sales invoices
            SELECT
                si.name,
                si.posting_date,
                si.project,
                si.customer,
                si.company,
                si.currency,

                cu.customer_name,
                cu.customer_group, 
                cu.territory,
                cu.default_discount as customer_default_discount,
                te.parent_territory as territory_parent,
                co.default_currency as company_currency

            FROM `tabSales Invoice` si
            JOIN `tabCustomer` cu ON cu.name = si.customer
            JOIN `tabTerritory` te ON te.name = cu.territory
            JOIN `tabCompany` co ON co.name = si.company
            WHERE si.docstatus = 1 %s %s 
        )

        SELECT -- Sales invoice items
            sii.name, 
            sii.parent as invoice,
            sinv.posting_date, 
            sinv.project, 
            sinv.customer, 
            sinv.company, 

            sii.item_code, 
            it.item_name,
            it.item_group, 
            ig.revenue_stream,
            it.description, 

            sii.sales_order,
            sii.delivery_note, 

            so.transaction_date as so_date,
            dn.posting_date as dn_date, 

            sii.income_account,
            sii.expense_account,
            sii.cost_center,

            sii.stock_qty,
            sii.stock_uom, 

            sinv.currency,
            sii.price_list_rate,
            sinv.customer_default_discount,
            sii.discount_percentage,
            sii.net_rate,
            sii.net_amount,
            sinv.company_currency,
            sii.base_price_list_rate,
            sii.base_net_rate,
            sii.base_net_amount, 

            sinv.customer_name,
            sinv.customer_group, 
            sinv.territory,
            sinv.territory_parent,

            sii.so_detail,
            sii.uom, 
            sii.qty,
            cogs.cogs as cogs,

            sr.name as service_report,
            sr.billing_basis,
            sii.enable_deferred_revenue

        FROM sinv
        LEFT JOIN `tabSales Invoice Item` sii ON sii.parent = sinv.name
        LEFT JOIN `tabItem` it ON it.item_code = sii.item_code
        LEFT JOIN `tabItem Group` ig ON ig.name = it.item_group
        LEFT JOIN cogs_per_sii cogs ON cogs.sii_name = sii.name
        LEFT JOIN `tabSales Order` so ON so.name = sii.sales_order
        LEFT JOIN `tabSales Order Item` soi ON soi.name = sii.so_detail
        LEFT JOIN `tabService Report` sr on sr.name = soi.service_report
        LEFT JOIN `tabDelivery Note` dn ON dn.name = sii.delivery_note

        UNION ALL
        
        SELECT -- taxes and charges
            t.name, 
            t.parent as invoice,
            sinv.posting_date, 
            sinv.project, 
            sinv.customer, 
            sinv.company, 

            NULL as item_code, 
            NULL as item_name,
            "Taxes and Charges" as item_group, 
            "Taxes and Charges" as revenue_stream, 
            t.description, 

            NULL as sales_order,
            NULL as delivery_note, 

            NULL as so_date,
            NULL as dn_date, 

            t.account_head as income_account,
            NULL as expense_account,
            t.cost_center,

            NULL as stock_qty,
            NULL as stock_uom, 

            sinv.currency,
            NULL price_list_rate,
            NULL as customer_default_discount,
            NULL as discount_percentage,
            NULL as net_rate,
            t.tax_amount as net_amount,
            sinv.company_currency,
            NULL as base_price_list_rate,
            NULL as base_net_rate,
            t.base_tax_amount as base_net_amount, 

            sinv.customer_name,
            sinv.customer_group, 
            sinv.territory,
            sinv.territory_parent,

            NULL as so_detail,
            NULL as uom, 
            NULL as qty,
            NULL as cogs,

            NULL as service_report,
            NULL as billing_basis,
            NULL as enable_deferred_revenue
        FROM sinv
        JOIN `tabSales Taxes and Charges` t ON t.parent = sinv.name
        

        ORDER BY posting_date DESC, invoice, item_code DESC
        """ % (conditions, match_conditions), filters, as_dict=1)
