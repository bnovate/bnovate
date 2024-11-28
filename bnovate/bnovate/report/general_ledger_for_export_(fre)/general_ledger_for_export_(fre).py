# Copyright (c) 2013, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _

from erpnext import get_company_currency, get_default_company


def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)

    return columns, data


def get_columns(filters):
    company = get_default_company()
    currency = get_company_currency(company)

    return [
        {
			"label": _("Posting Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 90
		},
		{
			"label": _("Account"),
			"fieldname": "account",
			"fieldtype": "Link",
			"options": "Account",
			"width": 180
		},
        {
            "label": "{0} ({1})".format(_("Debit"), currency),
            "fieldname": "debit",
            "fieldtype": "Float",
            "width": 100,
            "precision": 2
        },
        {
            "label": "{0} ({1})".format(_("Credit"), currency),
            "fieldname": "credit",
            "fieldtype": "Float",
            "width": 100,
            "precision": 2
        },
        {
            "label": "{0} ({1})".format(_("Balance"), currency),
            "fieldname": "balance",
            "fieldtype": "Float",
            "width": 130,
            "precision": 2
        },
        		{
			"label": _("Voucher Type"),
			"fieldname": "voucher_type",
			"width": 120
		},
		{
			"label": _("Voucher No"),
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 180
		},
		{
			"label": _("Against Account"),
			"fieldname": "against",
			"width": 120
		},
		{
			"label": _("Party Type"),
			"fieldname": "party_type",
			"width": 100
		},
		{
			"label": _("Party"),
			"fieldname": "party",
			"width": 100
		},
		{
			"label": _("Project"),
			"options": "Project",
			"fieldname": "project",
			"width": 100
		},
		{
			"label": _("Cost Center"),
			"options": "Cost Center",
			"fieldname": "cost_center",
			"width": 100
		},
		{
			"label": _("Against Voucher Type"),
			"fieldname": "against_voucher_type",
			"width": 100
		},
		{
			"label": _("Against Voucher"),
			"fieldname": "against_voucher",
			"fieldtype": "Dynamic Link",
			"options": "against_voucher_type",
			"width": 100
		},
		{
			"label": _("Supplier Invoice No"),
			"fieldname": "bill_no",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": _("Remarks"),
			"fieldname": "remarks",
			"width": 400
		},
		{
			"label": _("Item Names"),
			"fieldname": "item_names",
			"width": 400
		},
		{
			"label": _("Descriptions"),
			"fieldname": "descriptions",
			"width": 400
		},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 180
		},
    ]

    # Debit (CHF)	Credit (CHF)	Balance (CHF)	Voucher Type	Voucher No	Party Type	Party	Project	Cost Center	Against Voucher Type	Against Voucher	Supplier Invoice No	Remarks


def get_data(filters):

    conditions = ''
    if filters.account:
        conditions += 'AND gl.account = "{}"'.format(filters.account)
    if filters.company:
        conditions += 'AND gl.company = "{}"'.format(filters.company)
	

    sql = """
WITH labels AS (
  SELECT
	parent AS pinv,
	item_code,
	SUM(net_amount) as sum_amount,
	GROUP_CONCAT(item_name) AS item_names,
	GROUP_CONCAT(description) AS descriptions,
	expense_account,
	cost_center
  FROM `tabPurchase Invoice Item` poi
  GROUP BY parent, expense_account, cost_center
)
SELECT
    gl.posting_date,
    gl.account,
    gl.debit,
    gl.credit,
    NULL as balance,
    gl.voucher_type,
    gl.voucher_no,
    gl.against,
    gl.party_type,
    gl.party,
    gl.project,
    gl.cost_center,
    gl.against_voucher_type,
    gl.against_voucher,
	pinv.bill_no,
    gl.remarks,
    gl.company,
	labels.item_names,
    labels.descriptions,
    labels.sum_amount
FROM `tabGL Entry` gl
LEFT JOIN `tabPurchase Invoice` pinv ON gl.against_voucher = pinv.name
LEFT JOIN labels on labels.pinv = gl.voucher_no AND labels.expense_account = gl.account AND labels.cost_center = gl.cost_center
WHERE gl.posting_date BETWEEN "{from_date}" AND "{to_date}"
    {conditions}
ORDER BY gl.posting_date
    """.format(from_date=filters.from_date, to_date=filters.to_date, conditions=conditions)

    print("\n\n\n----------------\n\n\n")
    print(sql)
    
    return frappe.db.sql(sql, as_dict=True)