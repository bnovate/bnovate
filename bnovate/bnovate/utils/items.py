# (C) 2023, bNovate
#
# General utility functions for working with items

import frappe
from frappe.client import attach_file
from frappe.exceptions import DuplicateEntryError 

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
    """ Return next item code in naming series, with .01 suffix .

    Warning: avoid long prefixes, as unexpected behaviour may occur: 
    consider if item 200199 and 200200 exist. get_next_item_code('2001') will return 200200.01, which already exists
    
    """

    last_code = get_highest_item_code(prefix)
    if not last_code:
        return None
    
    try:
        last_code = int(last_code[:6])
    except ValueError:
        frappe.throw("Highest existing item can't be converted into a number: ", last_code)
    
    return "{}.01".format(last_code + 1)


@frappe.whitelist()
def get_item_codes(prefix):
    """ Return list of all item codes matching the prefix.
    
    For exact match, set prefix to the full item code:
    
    get_item_codes("100000.01")  # returns ["100000.01"]
    get_item_codes("100000")  # returns ["100000.01", "100000.02", ...]
    get_item_codes("1")  # returns ["100000.01", "100000.02", ..., "1000001.01", ...]

    """

    query = """
    --  --sql
SELECT item_code
FROM `tabItem`
WHERE item_code LIKE "{prefix}%"
;
    """.format(prefix=prefix)
    data = frappe.db.sql(query, as_dict=True)
    return [d.item_code for d in data]  


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
def get_item(item_code):
    """ Return item details for a given item code """
    item = frappe.get_doc("Item", item_code).as_dict()
    item["attachments"] = get_attachments(item_code)
    return item

def get_attachments(item_code):
    return frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Item",
            "attached_to_name": item_code,
        },
        fields=["name", "file_name", "file_url", "is_private"],
        order_by="creation asc",
    )

    
@frappe.whitelist()
def create_item(item_name, description, item_code=None, prefix="1"):
    """ Create item based on a naming series 

    Any files included in the form data will be attached to the item. If the form value name is "image", it will be attached to the image field of the item.
    
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

    upload_attachments(item_code)

    return item.name

    
@frappe.whitelist()
def upload_attachments(item_code, ignore_duplicate_error=False):
    """ Upload attachments to an item.  

    Any files included in the form data will be attached to the item. 
    If the form value name is "image", it will be attached to the image field of the item.

    If an identical file is uploaded twice to an item, frappe raises a DuplicateEntryError. 
    If ignore_duplicates is True, the error will be ignored. The result is that the correct file
    remains attached to the item. The response will be 200 OK but show the error message.
   
    """


    if not item_code:
        frappe.throw("Item code is required to upload attachments.")

    if not frappe.db.exists("Item", item_code):
        frappe.throw("Item does not exist: {0}".format(item_code))

    

    # Check for attachments. Special treatent if form value name is "image".
    for name, filestorage in frappe.request.files.items():
        print(name, filestorage)
        content = filestorage.stream.read()
        filename = filestorage.filename
        docfield = name == "image" and "image" or None

        try:
            file = attach_file(filename, content, "Item", item_code, docfield=docfield, is_private=1)
        except DuplicateEntryError as e:
            if ignore_duplicate_error:
                continue
            raise e


        
@frappe.whitelist()
def update_item(item_code, **kwargs):
    """ Update item details for a given item code. """
    changes = {"item_code": item_code}
    item = frappe.get_doc("Item", item_code)
    for key, value in kwargs.items():
        if hasattr(item, key):
            changes[key] = value
            setattr(item, key, value)
    item.save()

    upload_attachments(item_code, ignore_duplicate_error=True)

    return changes