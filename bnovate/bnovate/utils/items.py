# (C) 2023, bNovate
#
# General utility functions for working with items

import frappe
from frappe.client import attach_file

def get_highest_item_code(prefix=1):
    """ Return highest item code in a naming series """

    query = """
    --  --sql
SELECT MAX(item_code) as item_code
FROM `tabItem`
WHERE item_code LIKE "{prefix}%"
;
    """.format(prefix=prefix)
    data = frappe.db.sql(query, as_dict=True)
    if data:
        return data[0].item_code
    return None


@frappe.whitelist()
def get_next_item_code(prefix):
    """ Return next item code in naming series, with .01 suffix """

    last_code = get_highest_item_code(prefix)
    if not last_code:
        return None
    
    try:
        last_code = int(last_code[:6])
    except ValueError:
        frappe.throw("Highest existing item can't be converted into a number: ", last_code)
    
    return "{}.01".format(last_code + 1)


@frappe.whitelist()
def set_naming_series(prefix, number=0):
    """ Reset / modify naming series """
    res = frappe.db.sql("""
        UPDATE `tabSeries`
        SET current = {number}
        WHERE name LIKE "{prefix}"
    """.format(number=number, prefix=prefix))
    frappe.db.commit()
    return res

@frappe.whitelist()
def get_naming_series():
    return frappe.db.sql("SELECT * FROM `tabSeries`", as_dict=True)

    
@frappe.whitelist()
def create_item(item_name, description, item_code=None, prefix="1", image=None):
    """ Create item based on a naming series 

    
    Image should be a file attachment and will be set as the item image if provided.
    Additional form data supported:
    - image [file]: adds image as attachemnt and sets as cover image
    - any other file: adds as attachment
    
    """

    if not item_code:
        item_code = get_next_item_code(prefix)


    item = frappe.get_doc({
        "doctype": "Item",
        "item_code": item_code,
        "item_name": item_name,
        "description": description,
        "item_group": "R&D",
        "is_stock_item": 0,
        "has_variants": 0,
        "is_sales_item": 0,
        "is_purchase_item": 1
    })
    item.insert()

    # Check for attachments. Special treatent if form value name is "image".
    for name, filestorage in frappe.request.files.items():
        print(name, filestorage)
        content = filestorage.stream.read()
        filename = filestorage.filename
        docfield = name == "image" and "image" or None

        file = attach_file(filename, content, "Item", item_code, docfield=docfield, is_private=1)

    return item.name