# Copyright (c) 2013, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from erpnext import get_company_currency

from bnovate.bnovate.report.breakbulk_shipment_export.breakbulk_shipment_export import get_data as get_shipment_data


def execute(filters=None):
    columns, data = [], []
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {
            "label": "Line No",
            "fieldname": "dni_idx",
            "fieldtype": "Int",
            "width": 80
        },
        {
            "label": "Agr,ment",
            "fieldname": "agreement",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": "Invoice Number",
            "fieldname": "dn_name",
            "fieldtype": "Link",
            "options": "Delivery Note",
            "width": 150
        },
        {
            "label": "Invoice Date",
            "fieldname": "posting_date",
            "fieldtype": "Data",
            "width": 120

        },
        {
            "label": "Code Client",
            "fieldname": "customer_number",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": "Total Gross Weight",
            "fieldname": "total_gross_weight",
            "fieldtype": "Float",
            "width": 120
        },
        {
            "label": "Total Net Weight",
            "fieldname": "total_net_weight",
            "fieldtype": "Float",
            "width": 120
        },
        # {
        #     "label": "EORI",
        #     "fieldname": "eori_number",
        #     "fieldtype": "Data",
        #     "width": 150
        # },
        {
            "label": "Recipient's VAT Number",
            "fieldname": "tax_id",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": "Recipient's Country",
            "fieldname": "billing_country",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": "Item Name",
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": "Customs Tariff Number",
            "fieldname": "customs_tariff_number",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": "Net Weight",
            "fieldname": "dni_total_weight",
            "fieldtype": "Float",
            "width": 120
        },
        {
            "label": "Origin",
            "fieldname": "country_of_origin",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": "Preferential Origin",
            "fieldname": "preferential_origin",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": "Quantity Per Item",
            "fieldname": "qty",
            "fieldtype": "Float",
            "width": 120
        },
        {
            "label": "Items Value",
            "fieldname": "base_declared_amount",
            "fieldtype": "Float",
            "width": 120
        },
        {
            "label": "Currency",
            "fieldname": "currency",
            "fieldtype": "Data",
            "width": 80
        },
        {
            "label": "AWB Number",
            "fieldname": "breakbulk_master_no",
            "fieldtype": "Data",
            "width": 150
        }
    ]

def get_data(filters):

    # Fetch data from other report to ensure consistant filtering / value calculation.
    data = get_shipment_data(filters, include_parcels=False, include_shipping=True)

    # Get gross weight per breakbulk. Count each DN only once
    unique_weights = list(set((r['breakbulk_master_no'], r['dn_name'], r['dn_total_gross_weight']) for r in data))
    
    # Add ACL-specific data
    company_currency = get_company_currency(filters.company)
    for row in data:
        row.update({
            'agreement': 'S.',
            'customer_number': '',
            'preferential_origin': 'NO',
            'total_gross_weight': sum(el[2] for el in unique_weights if el[0] == row['breakbulk_master_no']),
            'total_net_weight': sum(r['dni_total_weight'] for r in data if r['breakbulk_master_no'] == row['breakbulk_master_no']),
        })

    return data


        
