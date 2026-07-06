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

    query = """
        SELECT
            dn.name AS shipperReference,
            COALESCE(a.company_name, dn.customer_name, '') AS receiverCompanyName,
            dn.contact_display AS receiverContactPersonName,
            a.address_line1 AS receiverAddressLine1,
            a.address_line2 AS receiverAddressLine2,
            "" AS receiverAddressLine3,
            a.pincode AS receiverPostalCode,
            a.city AS receiverCityName,
            UPPER(country.code) AS receiverCountryCode,
            a.phone AS receiverPhone,

            "B" AS productCode,
            "Water Monitoring Equipment" AS shipmentContentsDescription,

            dni.idx AS lineItemNumber,
            dni.item_name AS lineItemDescription,
            IF(dni.base_rate, dni.base_rate, dni.base_price_list_rate) AS lineItemUnitPrice,
            dni.qty AS lineItemQuantity,
            COALESCE(dni.country_of_origin, '') AS lineItemManufactureCountry,
            dni.total_weight AS lineItemNetWeight,
            dni.total_weight AS lineItemGrossWeight,
            COALESCE(dni.customs_tariff_number, '') AS lineItemExportCommodityCode,

            sp.count AS noOfPieces,
            sp.idx AS pieceNo,
            sp.length AS packageLength,
            sp.width AS packageWidth,
            sp.height AS packageHeight,
            sp.weight AS packageWeight

        FROM `tabDelivery Note Item` AS dni
        INNER JOIN `tabDelivery Note` AS dn ON dn.name = dni.parent
        LEFT JOIN `tabAddress` AS a ON a.name = dn.shipping_address_name
        LEFT JOIN `tabCountry` AS country ON country.name = a.country
        LEFT JOIN `tabContact` AS c ON c.name = dn.contact_person
        LEFT JOIN `tabShipment Parcel` AS sp ON sp.parent = dn.name

        WHERE dn.docstatus = 1
            AND dn.breakbulk_master_no IS NOT NULL AND TRIM(dn.breakbulk_master_no) != ''
            {filter_conditions}
        ORDER BY dn.name, dni.idx, sp.idx
    """.format(filter_conditions=filter_conditions)
    return frappe.db.sql(query, as_dict=1)
		
    
