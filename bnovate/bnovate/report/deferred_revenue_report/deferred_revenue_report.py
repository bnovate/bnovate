# Copyright (c) 2023, bNovate, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

def execute(filters=None):
    return get_columns(), get_data(filters)

def get_columns():
    return [
        {'fieldname': '', 'label': _(''), 'fieldtype': 'Data', 'width': 75},
        {'fieldname': 'invoice', 'label': _('Invoice'), 'fieldtype': 'Link', 'options': 'Sales Invoice', 'width': 100},
        {'fieldname': 'idx', 'label': _('Line'), 'fieldtype': 'Data', 'width': 50},
        {'fieldname': 'posting_date', 'label': _('Posting Date'), 'fieldtype': 'Date', 'width': 100},
        {'fieldname': 'invoiced_amount', 'label': _('Invoiced Amount'), 'fieldtype': 'Currency', 'options': 'account_currency', 'width': 150},
        {'fieldname': 'recognized_revenue', 'label': _('Recognized Amount'), 'fieldtype': 'Currency', 'options': 'account_currency', 'width': 150},
        {'fieldname': 'deferred_revenue', 'label': _('Deferred Amount'), 'fieldtype': 'Currency', 'options': 'account_currency', 'width': 150},
        {'fieldname': 'item_code', 'label': _('Item'), 'fieldtype': 'Link', 'options': 'Item', 'width': 200},
        {'fieldname': 'service_start_date', 'label': _('Service Start Date'), 'fieldtype': 'Date', 'width': 100},
        {'fieldname': 'service_end_date', 'label': _('Service End Date'), 'fieldtype': 'Date', 'width': 100},
        # {'fieldname': 'docstatus', 'label': _('Status'), 'fieldtype': 'Data', 'width': 100},
        # {'fieldname': 'status', 'label': _('Status'), 'fieldtype': 'Data', 'width': 100},
        {'fieldname': 'account', 'label': _('Account'), 'fieldtype': 'data', 'width': 200},
        {'fieldname': 'type', 'label': _('Type'), 'fieldtype': 'data', 'width': 200},
    ]


def get_data(filters):
    account = filters.account
    # if not account:
    #     return
    sql_query = """
WITH rr AS ( -- recognized revenue
  SELECT
    inv.name AS doc,
    inv_item.idx,
 		inv_item.name as detail_docname,
    inv.posting_date as doc_posting_date,
    inv_item.item_code,
    i.item_name,

    inv_item.service_start_date,
    inv_item.service_end_date,
    inv_item.base_net_amount,
    inv_item.deferred_revenue_account as account,

    gle.posting_date AS gle_posting_date,
    gle.debit AS debit,
    gle.credit AS credit,
    gle.account_currency,
  	RANK() OVER (PARTITION BY gle.account, inv_item.parent, inv_item.name ORDER BY gle.posting_date) AS detail_rank -- used to filter out duplicates
  FROM `tabSales Invoice Item` inv_item
  JOIN `tabSales Invoice` inv ON inv.name = inv_item.parent
  JOIN `tabItem` i on i.name = inv_item.item_code
  LEFT JOIN ( SELECT * FROM `tabGL Entry` 
             WHERE posting_date <= "{to_date}" 
             AND account IN (SELECT DISTINCT(deferred_revenue_account)
														FROM `tabSales Invoice Item`
														WHERE enable_deferred_revenue = 1
														AND docstatus = 1)
	) AS gle ON inv_item.name = gle.voucher_detail_no
  WHERE inv.docstatus = 1
    AND inv_item.enable_deferred_revenue = 1
)

SELECT
	*,
  SUM(debit) OVER (PARTITION BY account, detail_docname) AS item_recognized_revenue,
  SUM(debit) OVER (PARTITION BY account, doc) AS doc_recognized_revenue,
  SUM(IF(detail_rank = 1, base_net_amount, 0)) OVER (PARTITION BY account, doc) AS doc_invoiced_amount, -- initial total of deferred amounts

  SUM(debit) OVER (PARTITION BY account) AS account_recognized_revenue,
  SUM(IF(detail_rank = 1, base_net_amount, 0)) OVER (PARTITION BY account) AS account_invoiced_amount
FROM rr
ORDER BY account, doc_posting_date, doc, idx, gle_posting_date
    """.format(to_date=filters.to_date)
    data = frappe.db.sql(sql_query, as_dict=True)

    # Go through lines. If we find a new invoice or item, insert a node:
    out = []
    prev_row = {}
    total_deferred = 0
    for row in data:
        if not prev_row or prev_row.account != row.account:
            # New account
            deferred = row.account_invoiced_amount - ( row.account_recognized_revenue if row.account_recognized_revenue else 0) 
            out.append({
                'indent': 0,
                'account': row.account,
                'invoiced_amount': row.account_invoiced_amount, # row.net_amount,
                'recognized_revenue': row.account_recognized_revenue,
                'deferred_revenue': deferred,
                'type': "Account",
            })

        if not prev_row or prev_row.doc != row.doc:
            # New invoice
            deferred = row.doc_invoiced_amount - ( row.doc_recognized_revenue if row.doc_recognized_revenue else 0)
            total_deferred += deferred
            out.append({
                'indent': 1,
                'invoice': row.doc,
                'posting_date': row.doc_posting_date,
                'invoiced_amount': row.doc_invoiced_amount, # row.net_amount,
                'recognized_revenue': row.doc_recognized_revenue,
                'deferred_revenue': deferred,
                'type': "Invoice",
            })

        if not prev_row or prev_row.detail_docname != row.detail_docname:
            # New invoice item
            recognized = row.item_recognized_revenue if row.item_recognized_revenue else 0
            out.append({
                'indent': 2,
                'idx': row.idx,
                'invoiced_amount': row.base_net_amount,
                'recognized_revenue': recognized,
                'deferred_revenue': row.base_net_amount - recognized, #row.net_amount - row.item_recognized_revenue,
                'item_code': row.item_code,
                'item_name': row.item_name,
                'service_start_date': row.service_start_date,
                'service_end_date': row.service_end_date,
                'type': "Invoice Item",
            })

        prev_row = row.copy()

        row.indent = 3
        row.posting_date = row.gle_posting_date
        row.recognized_revenue = row.debit
        row.type = "Ledger Entry"
        row.service_start_date = None
        row.service_end_date = None
        row.item_code = None
        row.item_name = None
        out.append(row)

    # Get Balance and compare
    return out

    sql_query = """
SELECT
  SUM(debit) - SUM(credit) as balance
FROM `tabGL Entry`
WHERE account LIKE "%Deferred%"
AND posting_date <= "{to_date}"
    """.format(to_date=filters.to_date)
    data = frappe.db.sql(sql_query, as_dict=True)
    balance = 0
    if data:
        balance = -data[0].balance

    # Add totals
    out = [{
        'indent': 0,
        'deferred_revenue': balance,
        'account': prev_row.account,
    }, {
        'indent': 0,
        'deferred_revenue': total_deferred,
        'account': 'Sum of invoices'
    }] + out

    return out