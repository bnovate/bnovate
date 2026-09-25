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

    
# TODO: check that odd-items are only ever part of R&D group?

    
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
    old_item_group = item.item_group
    for key, value in kwargs.items():
        if hasattr(item, key):
            changes[key] = value
            setattr(item, key, value)

    # Item defaults are specific to an item group: if the item group changes,
    # the existing defaults (default warehouse, price lists, taxes, ...) no
    # longer apply and are cleared.
    if changes.get("item_group") and changes["item_group"] != old_item_group:
        item.set("item_defaults", [])
        changes["item_defaults"] = []

    item.save()

    upload_attachments(item_code, ignore_duplicate_error=True)

    return changes


# Fields managed automatically by Frappe. They are metadata, not business
# data, and must NOT be copied when duplicating a document:
#   - name / naming_series : identity, replaced by the new item code
#   - owner, creation, modified, modified_by : audit trail, regenerated on insert
#   - docstatus, idx, parent, parentfield, parenttype : workflow / tree position
#   - __islocal, __onload, ... : transient keys that never belong in the DB
# Everything else (including all child tables) is data and gets copied.
METADATA_FIELDS = (
    "name",
    "naming_series",
    "owner",
    "creation",
    "modified",
    "modified_by",
    "docstatus",
    "idx",
    "parent",
    "parentfield",
    "parenttype",
    "__islocal",
    "__onload",
    "__unedited",
    "__newname",
)


def _strip_metadata(doc_dict):
    """ Return a copy of a document dict (frappe._dict or plain dict) without
    any metadata fields, recursively for child table rows. The "doctype" key
    is kept so frappe.get_doc() can rebuild the document. """
    cleaned = {k: v for k, v in doc_dict.items() if k not in METADATA_FIELDS}

    for key, value in cleaned.items():
        if isinstance(value, list) and value and isinstance(value[0], dict) and "doctype" in value[0]:
            cleaned[key] = [_strip_metadata(row) for row in value]

    return cleaned


@frappe.whitelist()
def duplicate_item(item_code, new_item_code):
    """ Duplicate an existing Item under a new item code.

    Copies all data fields, including child tables (barcodes, UOM conversions,
    item defaults, taxes, ...). Metadata (name, owner, creation, modified, ...)
    is discarded and regenerated by Frappe on insert. Attachments are not copied.

    Returns the name of the newly created item.
    """

    if not frappe.db.exists("Item", item_code):
        frappe.throw("Item {} does not exist".format(item_code))

    if frappe.db.exists("Item", new_item_code):
        frappe.throw("Item {} already exists".format(new_item_code))

    source = frappe.get_doc("Item", item_code)

    data = _strip_metadata(source.as_dict())
    data["item_code"] = new_item_code

    new_item = frappe.get_doc(data)
    # Item is autonamed by item_code ("field:item_code"), so set it explicitly
    # to guarantee the document name matches the requested code.
    new_item.name = new_item_code
    new_item.insert()

    return new_item.name