# Copyright (c) 2013, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	return get_columns(), get_data(filters)

 
def get_columns():
    return [
        {"label": "Shipper Reference", "fieldname": "shipperReference", "fieldtype": "Link", "options": "Delivery Note", "width": 140},
        {"label": "Receiver Company Name", "fieldname": "receiverCompanyName", "fieldtype": "Data", "width": 180},
        {"label": "Receiver Contact Person Name", "fieldname": "receiverContactPersonName", "fieldtype": "Data", "width": 180},
        {"label": "Receiver Address Line 1", "fieldname": "receiverAddressLine1", "fieldtype": "Data", "width": 180},
        {"label": "Receiver Address Line 2", "fieldname": "receiverAddressLine2", "fieldtype": "Data", "width": 180},
        {"label": "Receiver Address Line 3", "fieldname": "receiverAddressLine3", "fieldtype": "Data", "width": 180},
        {"label": "Receiver Postal Code", "fieldname": "receiverPostalCode", "fieldtype": "Data", "width": 110},
        {"label": "Receiver City Name", "fieldname": "receiverCityName", "fieldtype": "Data", "width": 140},
        {"label": "Receiver Country Code", "fieldname": "receiverCountryCode", "fieldtype": "Data", "width": 120},
        {"label": "Receiver Email", "fieldname": "receiverEmail", "fieldtype": "Data", "width": 130},
        {"label": "Receiver Phone", "fieldname": "receiverPhone", "fieldtype": "Data", "width": 130},
        {"label": "Product Code", "fieldname": "productCode", "fieldtype": "Data", "width": 100},
        {"label": "Shipment Contents Description", "fieldname": "shipmentContentsDescription", "fieldtype": "Data", "width": 220},
        {"label": "Line Item Number", "fieldname": "lineItemNumber", "fieldtype": "Int", "width": 100},
        {"label": "Line Item Description", "fieldname": "lineItemDescription", "fieldtype": "Data", "width": 220},
        {"label": "Line Item Unit Price", "fieldname": "lineItemUnitPrice", "fieldtype": "Float", "width": 120},
        {"label": "Line Item Quantity", "fieldname": "lineItemQuantity", "fieldtype": "Float", "width": 120},
        {"label": "Line Item Manufacture Country", "fieldname": "lineItemManufactureCountry", "fieldtype": "Data", "width": 140},
        {"label": "Line Item Net Weight", "fieldname": "lineItemNetWeight", "fieldtype": "Float", "width": 120},
        {"label": "Line Item Gross Weight", "fieldname": "lineItemGrossWeight", "fieldtype": "Float", "width": 120},
        {"label": "Line Item Export Commodity Code", "fieldname": "lineItemExportCommodityCode", "fieldtype": "Data", "width": 160},
        {"label": "No Of Pieces", "fieldname": "noOfPieces", "fieldtype": "Int", "width": 90},
        {"label": "Piece No", "fieldname": "pieceNo", "fieldtype": "Int", "width": 80},
        {"label": "Package Length", "fieldname": "packageLength", "fieldtype": "Float", "width": 110},
        {"label": "Package Width", "fieldname": "packageWidth", "fieldtype": "Float", "width": 110},
        {"label": "Package Height", "fieldname": "packageHeight", "fieldtype": "Float", "width": 110},
        {"label": "Package Weight", "fieldname": "packageWeight", "fieldtype": "Float", "width": 110},
    ]


def get_data(filters):
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
      dn.name AS shipperReference,
      COALESCE(a.company_name, dn.customer_name, '') AS receiverCompanyName,
      COALESCE(a.contact_name, dn.contact_display) AS receiverContactPersonName,
      a.address_line1 AS receiverAddressLine1,
      a.address_line2 AS receiverAddressLine2,
      "" AS receiverAddressLine3,
      a.pincode AS receiverPostalCode,
      a.city AS receiverCityName,
      UPPER(country.code) AS receiverCountryCode,
      a.email_id AS receiverEmail,
      a.phone AS receiverPhone,

      "B" AS productCode,
      "Water Monitoring Equipment" AS shipmentContentsDescription

    FROM `tabDelivery Note` dn
    LEFT JOIN `tabAddress` a ON a.name = dn.shipping_address_name
    LEFT JOIN `tabCountry` country ON country.name = a.country
    LEFT JOIN `tabContact` c ON c.name = dn.contact_person

    WHERE dn.docstatus = 1
        AND dn.breakbulk_master_no IS NOT NULL AND TRIM(dn.breakbulk_master_no) != ''
        {filter_conditions}

    ORDER BY dn.name

    """.format(filter_conditions=filter_conditions), as_dict=1)

    for dn in dns:
        dn_items = frappe.db.sql("""
            SELECT
                dni.idx AS lineItemNumber,
                dni.item_name AS lineItemDescription,
                COALESCE(NULLIF(dni.base_rate, 0), NULLIF(dni.base_price_list_rate, 0), item.return_value) AS lineItemUnitPrice,
                dni.qty AS lineItemQuantity,
                COALESCE(dni.country_of_origin, '') AS lineItemManufactureCountry,
                dni.total_weight AS lineItemNetWeight,
                dni.total_weight AS lineItemGrossWeight,
                COALESCE(dni.customs_tariff_number, '') AS lineItemExportCommodityCode,

                dni.base_rate,
                dni.hide_price,
                item.is_stock_item,
                dni.force_declaration,
                (SELECT COUNT(pi.name) FROM `tabPacked Item` pi WHERE pi.parent_detail_docname = dni.name) as packed_items

            FROM `tabDelivery Note Item` dni
            LEFT JOIN `tabItem` item ON item.item_code = dni.item_code 

            WHERE dni.parent = '{dn_name}'

            ORDER BY dni.idx
        """.format(dn_name=dn.shipperReference), as_dict=1)

        
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


        dn_parcels = frappe.db.sql("""
            SELECT
                sp.count AS noOfPieces,
                sp.idx AS pieceNo,
                sp.length AS packageLength,
                sp.width AS packageWidth,
                sp.height AS packageHeight,
                sp.weight AS packageWeight
            FROM `tabShipment Parcel` sp

            WHERE sp.parent = '{dn_name}'
        """.format(dn_name=dn.shipperReference), as_dict=1)

        print(dn.shipperReference, len(dn_parcels))

        dn['items'] = dn_items
        dn['parcels'] = dn_parcels

    data = []


    for dn in dns:

        while len(dn['items']) > 0 or len(dn['parcels']) > 0:
            it = dn['items'].pop(0) if len(dn['items']) > 0 else {'lineItemDescription': 'PLACEHOLDER', 'lineItemUnitPrice': 1.0, 'lineItemQuantity': 1.0}
            sp = dn['parcels'].pop(0) if len(dn['parcels']) > 0 else {}

            row = {**dn, **it, **sp}
            data.append(row)

    return data

    
