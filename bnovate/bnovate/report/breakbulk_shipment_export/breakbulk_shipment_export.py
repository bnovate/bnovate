# Copyright (c) 2013, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from erpnext import get_company_currency

def execute(filters=None):
	return get_columns(), get_data(filters)

 
def get_columns():
    return [
        {"label": "Shipper Reference", "fieldname": "dn_name", "fieldtype": "Link", "options": "Delivery Note", "width": 140},
        {"label": "Receiver Company Name", "fieldname": "delivery_company_name", "fieldtype": "Data", "width": 180},
        {"label": "Receiver Contact Person Name", "fieldname": "delivery_contact_name", "fieldtype": "Data", "width": 180},
        {"label": "Receiver Address Line 1", "fieldname": "delivery_address_line1", "fieldtype": "Data", "width": 180},
        {"label": "Receiver Address Line 2", "fieldname": "delivery_address_line2", "fieldtype": "Data", "width": 180},
        {"label": "Receiver Address Line 3", "fieldname": "delivery_address_line3", "fieldtype": "Data", "width": 180},
        {"label": "Receiver Postal Code", "fieldname": "delivery_postal_code", "fieldtype": "Data", "width": 110},
        {"label": "Receiver City Name", "fieldname": "delivery_city", "fieldtype": "Data", "width": 140},
        {"label": "Receiver Country Code", "fieldname": "delivery_country_code", "fieldtype": "Data", "width": 120},
        {"label": "Receiver Email", "fieldname": "delivery_email", "fieldtype": "Data", "width": 130},
        {"label": "Receiver Phone", "fieldname": "delivery_phone", "fieldtype": "Data", "width": 130},

        {"label": "Product Code", "fieldname": "product_code", "fieldtype": "Data", "width": 100},
        {"label": "Shipment Contents Description", "fieldname": "contents_description", "fieldtype": "Data", "width": 220},

        {"label": "Line Item Number", "fieldname": "dni_idx", "fieldtype": "Int", "width": 100},
        {"label": "Line Item Description", "fieldname": "item_name", "fieldtype": "Data", "width": 220},
        {"label": "Line Item Unit Price", "fieldname": "base_declared_rate", "fieldtype": "Float", "width": 120},
        {"label": "Line Item Quantity", "fieldname": "qty", "fieldtype": "Float", "width": 120},
        {"label": "Line Item Manufacture Country", "fieldname": "country_of_origin", "fieldtype": "Data", "width": 140},
        {"label": "Line Item Net Weight", "fieldname": "dni_total_weight", "fieldtype": "Float", "width": 120},
        {"label": "Line Item Gross Weight", "fieldname": "dni_total_weight", "fieldtype": "Float", "width": 120},
        {"label": "Line Item Export Commodity Code", "fieldname": "customs_tariff_number", "fieldtype": "Data", "width": 160},

        {"label": "No Of Pieces", "fieldname": "sp_count", "fieldtype": "Int", "width": 90},
        {"label": "Piece No", "fieldname": "sp_idx", "fieldtype": "Int", "width": 80},
        {"label": "Package Length", "fieldname": "sp_length", "fieldtype": "Float", "width": 110},
        {"label": "Package Width", "fieldname": "sp_width", "fieldtype": "Float", "width": 110},
        {"label": "Package Height", "fieldname": "sp_height", "fieldtype": "Float", "width": 110},
        {"label": "Package Weight", "fieldname": "sp_weight", "fieldtype": "Float", "width": 110},
    ]


def get_data(filters, include_parcels=True, include_shipping=False):

    shipping_default_account = frappe.get_value("Company", filters.company, "default_freight_sales_account")
    company_currency = get_company_currency(filters.company)

    filter_conditions = ""
    if filters.mawb:
        filter_conditions += " AND dn.breakbulk_master_no = '{mawb}'".format(mawb=filters.mawb)

    # Build expected structure of the CSV file: one row per item, but also per parcel.
    # If more items than parcels, cells describing parcels can be empty.
    # If more parcels than items, cells describing items can't be empty, so fill with an obvious placeholder.

    # This format is hard to build with a SQL query, so we query the DN, items, and the parcels separately. 
    # Items are fitlered to remove items that are irrelevant for a custom's declaration.

    dns = frappe.db.sql("""
    SELECT
      dn.breakbulk_master_no,
      dn.name AS dn_name,
      DATE_FORMAT(dn.posting_date, '%Y%m%d') as posting_date,

      # Shipping
      COALESCE(a.company_name, dn.customer_name, '') AS delivery_company_name,
      COALESCE(a.contact_name, dn.contact_display) AS delivery_contact_name,
      a.address_line1 AS delivery_address_line1,
      a.address_line2 AS delivery_address_line2,
      "" AS delivery_address_line3,
      a.pincode AS delivery_postal_code,
      a.city AS delivery_city,
      UPPER(country.code) AS delivery_country_code,
      a.email_id AS delivery_email,
      a.phone AS delivery_phone,

      # Billing
      dn.eori_number,
      REGEXP_REPLACE(dn.tax_id, '[^a-zA-Z0-9]', '') as tax_id,
      billing_addr.country as billing_country,

      "B" AS product_code,  # DHL specific
      "Water Monitoring Equipment"  AS contents_description, # DHL specific
      dn.total_gross_weight AS dn_total_gross_weight,
      "{company_currency}" AS currency

    FROM `tabDelivery Note` dn
    LEFT JOIN `tabAddress` a ON a.name = dn.shipping_address_name
    LEFT JOIN `tabAddress` billing_addr ON billing_addr.name = dn.customer_address
    LEFT JOIN `tabCountry` country ON country.name = a.country
    LEFT JOIN `tabContact` c ON c.name = dn.contact_person

    WHERE dn.docstatus = 1
        AND dn.breakbulk_master_no IS NOT NULL AND TRIM(dn.breakbulk_master_no) != ''
        {filter_conditions}

    ORDER BY dn.name

    """.format(filter_conditions=filter_conditions, company_currency=company_currency), as_dict=1)

    for dn in dns:
        dn_items = frappe.db.sql("""
            SELECT
                dni.idx AS dni_idx,
                dni.item_name AS item_name,
                COALESCE(NULLIF(dni.base_rate, 0), NULLIF(dni.base_price_list_rate, 0), item.return_value) AS base_declared_rate,
                COALESCE(NULLIF(dni.base_amount, 0), NULLIF(dni.base_price_list_rate * dni.qty, 0), item.return_value * dni.qty) AS base_declared_amount,
                dni.qty AS qty,
                COALESCE(dni.country_of_origin, '') AS country_of_origin,
                dni.total_weight AS dni_total_weight,
                COALESCE(dni.customs_tariff_number, '') AS customs_tariff_number,

                dni.base_rate,  # original base rate, used to filter out bundled items
                dni.hide_price,
                item.is_stock_item,
                dni.force_declaration,
                (SELECT COUNT(pi.name) FROM `tabPacked Item` pi WHERE pi.parent_detail_docname = dni.name) as packed_items

            FROM `tabDelivery Note Item` dni
            LEFT JOIN `tabItem` item ON item.item_code = dni.item_code 

            WHERE dni.parent = '{dn_name}'

            UNION ALL  # Add shipping, but only if required (see WHERE filters)

            SELECT
                0 as dni_idx,
                tc.description as item_name,
                tc.base_tax_amount as base_declared_rate,
                tc.base_tax_amount as base_amount,
                1 as qty,
                "" as country_of_origin,
                0 as dni_total_weight,
                "" as customs_tariff_number,

                tc.base_tax_amount as base_rate,  # not used for shipping anyway
                0 as hide_price,
                0 as is_stock_item,
                1 as force_declaration,
                0 as packed_items

            FROM `tabSales Taxes and Charges` tc
            LEFT JOIN `tabDelivery Note` dn ON tc.parent = dn.name

            WHERE {include_shipping}
                AND tc.parent = '{dn_name}'
                AND tc.account_head = '{shipping_default_account}'
                AND tc.tax_amount > 0

            ORDER BY dni_idx
        """.format(dn_name=dn.dn_name, include_shipping=include_shipping, shipping_default_account=shipping_default_account), as_dict=1)

        
        # Remove items following same rules as commercial invoice.
        for row in dn_items[:]:
            # Allow manual override:
            if row.force_declaration:
                continue

            # Remove bundled power supply and other items with price included elsewhere
            if row.hide_price and row.base_rate == 0.0:
                dn_items.remove(row)
                continue

            # Keep bundle masters:
            if row.packed_items > 0:
                continue

            # Remove non-stock items
            if not row.is_stock_item:
                dn_items.remove(row)
                continue


        dn_parcels = []
        if include_parcels:
            dn_parcels = frappe.db.sql("""
                SELECT
                    sp.count AS sp_count,
                    sp.idx AS sp_idx,
                    sp.length AS sp_length,
                    sp.width AS sp_width,
                    sp.height AS sp_height,
                    sp.weight AS sp_weight
                FROM `tabShipment Parcel` sp

                WHERE sp.parent = '{dn_name}'
            """.format(dn_name=dn.dn_name), as_dict=1)

        dn['items'] = dn_items
        dn['parcels'] = dn_parcels

    data = []


    for dn in dns:

        while len(dn['items']) > 0 or len(dn['parcels']) > 0:
            it = dn['items'].pop(0) if len(dn['items']) > 0 else {'item_name': 'PLACEHOLDER', 'base_rate': 1.0, 'qty': 1.0}
            sp = dn['parcels'].pop(0) if len(dn['parcels']) > 0 else {}

            row = {**dn, **it, **sp}
            data.append(row)

    return data

    
