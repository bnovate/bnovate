# Copyright (c) 2013-2023, bnovate, libracore and contributors
# For license information, please see license.txt

import frappe
import urllib

from bnovate.bnovate.utils.shipping import quick_validate_address, AddressError

from frappe import _

from frappe.contacts.doctype.address.address import get_address_display


def auth(context):
    """ check login, throw exception if not logged in """
    frappe.local.return_to_path = "/" + context.pathname

    if frappe.session.user=='Guest' or not "@" in frappe.session.user:
        frappe.throw(_("You need to be logged in to access this page"), frappe.PermissionError)

def is_guest():
    if frappe.session.user=='Administrator':
        return False
    if frappe.session.user=='Guest' or not "@" in frappe.session.user:
        return True
    return False

def is_desk_user():
    """ Return True if current user has access to Desk """
    if frappe.session.user=='Administrator':
        return True
    if is_guest():
        return False
    user_type = frappe.db.get_value("User", {"name": frappe.session.user}, "user_type")
    if user_type == "System User":
        return True
    return False

def is_system_user():
    return is_desk_user()

LANGUAGES = [
    {"code": "en", "name": "English"},
    {"code": "fr", "name": "Français"},
    {"code": "de", "name": "Deutsch"},
]

def update_context(context):
    """ Called by hooks.py as a 'middleware' on all pages, including Desk pages. """
    build_sidebar(context, context.show_sidebar)

    add_language_menu(context)
    return context

def add_language_menu(context):
    """ Add a language dropdown to the navbar, right after the Help item.

    Only useful to logged in users, since it sets the default language stored on their User.
    Entries are rendered by frappe's navbar_items.html: the `target` of an item is printed as
    raw attributes of its link, which is how data-lang gets there (picked up by helpers.js).
    """
    if context.get("top_bar_items") is None or is_guest():
        return

    current = next((l for l in LANGUAGES if l["code"] == frappe.local.lang), LANGUAGES[0])
    children = []
    for lang in LANGUAGES:
        is_current = lang["code"] == current["code"]
        children.append(frappe._dict(
            label=("&#10003; " if is_current else "&emsp; ") + lang["name"],
            url="/",
            target='data-lang="{0}"{1}'.format(lang["code"], " data-current" if is_current else ""),
        ))

    menu = frappe._dict(
        label='<i class="fa fa-globe"></i> ' + current["name"],
        right=1,
        parent_label=None,
        child_items=children,
    )
    # New list: the one in context may be shared between requests
    context.top_bar_items = list(context.top_bar_items) + [menu]

@frappe.whitelist()
def set_language(lang):
    """ Change the default language of the logged in user """
    if lang not in [l["code"] for l in LANGUAGES]:
        frappe.throw(_("Unsupported language"))
    if is_guest():
        frappe.throw(_("You need to be logged in to access this page"), frappe.PermissionError)

    user = frappe.get_doc("User", frappe.session.user)
    user.language = lang
    user.save(ignore_permissions=True)
    frappe.db.commit()

def get_settings():
    return frappe.get_single("bNovate Settings")

def get_session_customers():
    # fetch customers for this user, ordered the same as in Desk.
    customers = frappe.db.sql("""
        SELECT 
            `tC1`.`link_name` AS `docname`,
            `tCus`.`enable_cartridge_portal`,
            `tCus`.`allow_unstored_cartridges`,
            `tCus`.`customer_name`,
            `tCus`.`portal_billing_address`,
            `tCus`.`organize_return`,
            `tCus`.`is_service_partner`
        FROM `tabContact`
        JOIN `tabDynamic Link` AS `tC1` ON `tC1`.`parenttype` = "Contact" 
                                       AND `tC1`.`link_doctype` = "Customer" 
                                       AND `tC1`.`parent` = `tabContact`.`name`
        JOIN `tabCustomer` as `tCus` ON `tCus`.`name` = `tC1`.`link_name`
        WHERE `tabContact`.`user` = "{user}"
        ORDER BY `tC1`.`idx`;
    """.format(user=frappe.session.user), as_dict=True)

    return customers

def get_session_primary_customer():
    """ Return details of primary customer, i.e. first in list of linked customers """
    customers = get_session_customers()
    if customers:
        return customers[0]
    else:
        return None

def get_session_contact():
    """ Return names of contacts associated to this user id """

    # Note: I prevent a user from owning several contacts by setting User ID to unique in Contact doctype

    users = frappe.db.sql("""
    SELECT
        name
    FROM tabContact tc
    WHERE tc.user = "{user}"
    """.format(user=frappe.session.user), as_dict=True)

    return users[0].name

def has_cartridge_portal():
    """ True if user is allowed to use cartridge management features """
    customer = get_session_primary_customer()
    if customer is not None and customer.enable_cartridge_portal:
        return True
    return False

def is_service_partner():
    """ True if user's primary Customer is a service partner """
    primary_customer = get_session_primary_customer()
    if primary_customer is None:
        return False
    else:
        return bool(primary_customer.is_service_partner)


def allow_unstored_cartridges():
    """ True if user is allowed to use cartridge management features """
    customer = get_session_primary_customer()
    if customer is not None and customer.allow_unstored_cartridges:
        return True
    return False

def organize_return():
    """ True if we manage return logistics for refill requests """
    customer = get_session_primary_customer()
    if customer is not None and customer.organize_return:
        return True
    return False

def fixed_billing_address():
    """ Links to a billing address if customer CAN'T change his address """
    # This is required by some key accounts: allow users to order cartridges to their 
    # shipping address but not mess with invoicing data.

    customer = get_session_primary_customer()
    if customer is not None: 
        return customer.portal_billing_address
    return None


def build_sidebar(context, show=True):
    context.show_sidebar = show
    context.sidebar_items = [{
            'route': '/',
            'title': 'Dashboard',
        }, {
            'route': '/quotations',
            'title': 'Quotations',
        }, {
            'route': '/invoices',
            'title': 'Invoices',
        }, {
            'route': '/instruments',
            'title': 'Instruments',
        }]

    if has_cartridge_portal():
        context.sidebar_items.extend([{
                'route': '/cartridges',
                'title': 'Cartridges',
            }, {
                'route': '/requests',
                'title': 'Refill Requests',
            }, {
                'route': '/my_addresses',
                'title': 'Addresses',
            }])

@frappe.whitelist()
def get_addresses():
    """ Return addresses for the current contact """
    addresses = frappe.db.sql("""
        SELECT DISTINCT -- avoid duplicates when address is linked to two customers.
            `tabAddress`.`name`,
            `tabAddress`.`company_name`,
            `tabAddress`.`contact_name`,
            `tabAddress`.`address_type`,
            `tabAddress`.`address_line1`,
            `tabAddress`.`address_line2`,
            `tabAddress`.`pincode`,
            `tabAddress`.`city`,
            `tabAddress`.`country`,
            `tabAddress`.`is_primary_address`,
            `tabAddress`.`is_shipping_address`,
            `tabAddress`.`phone`,
            `tabAddress`.`email_id`
            -- , `tC1`.`link_name` AS `customer_docname`
        FROM `tabContact`
        JOIN `tabDynamic Link` AS `tC1` ON `tC1`.`parenttype` = "Contact" 
                                       AND `tC1`.`link_doctype` = "Customer" 
                                       AND `tC1`.`parent` = `tabContact`.`name`
        JOIN `tabDynamic Link` AS `tA1` ON `tA1`.`parenttype` = "Address" 
                                       AND `tA1`.`link_doctype` = "Customer" 
                                       AND `tA1`.`link_name` = `tC1`.`link_name`
        LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tA1`.`parent`
        WHERE `tabContact`.`user` = "{user}"
            AND NOT `tabAddress`.`portal_hide`
        ORDER BY `tabAddress`.`company_name`, `tabAddress`.`address_line1`
    """.format(user=frappe.session.user), as_dict=True)

    for addr in addresses:
        short_addr = addr.copy();
        # if 'email_id' in short_addr:
        #     # del short_addr['email_id']
        #     pass
        addr.display = get_address_display(short_addr)

    
    return addresses

@frappe.whitelist()
def get_address_data():
    """ Return list of addresses and dedicated billing address if relevant """
    billing_address = fixed_billing_address()
    all_addresses = get_addresses()
    shipping_addresses = [a for a in all_addresses if a.name != billing_address]
    
    # Can be made fancier later:
    if billing_address:
        billing_addresses = [a for a in all_addresses if a.name == billing_address]
    else:
        billing_addresses = all_addresses

    return frappe._dict({
        "addresses": all_addresses,
        "shipping_addresses": shipping_addresses,
        "billing_addresses": billing_addresses,
        "fixed_billing_address": billing_address,
    })


@frappe.whitelist()
def create_address(address_line1, pincode, city, address_type="Shipping", company_name=None, contact_name=None, address_line2=None, country="Switzerland", phone="", email_id="", commit=True):
    """ Add address on primary customer associated to this user """

    # Check deliverability
    try:
        quick_validate_address(pincode, country)
    except AddressError:
        frappe.msgprint(
            msg=_("Our carrier can't ship to this address. Please check Postal Code."),
            title="Error",
            indicator="red",
            raise_exception=AddressError,
        )

    # fetch customers for this user
    customer = get_session_primary_customer()
    customer_links = [{'link_doctype': 'Customer', 'link_name': customer.docname}]
    # create new address
    pure_name = "{0}-{1}-{2}-{3}".format(customer.docname, company_name, address_line1, city).replace(" ", "_").replace("&", "and").replace("+", "and").replace("?", "-").replace("=", "-")
    new_address = frappe.get_doc({
        'doctype': 'Address',
        'address_title': pure_name,
        'company_name': company_name,
        'contact_name': contact_name,
        'address_type': address_type,
        'address_line1': address_line1,
        'address_line2': address_line2,
        'pincode': pincode,
        'city': city,
        'country': country,
        'links': customer_links,
        'phone': phone,
        'email_id': email_id,
    })
    
    new_address.insert(ignore_permissions=True)
    if commit:
        frappe.db.commit()


@frappe.whitelist()
def delete_address(name):
    """ Unlink all customers from this address """
    # fetch customers for this user
    customers = get_session_customers()
    address = frappe.get_doc("Address", name)
    permitted = False
    for l in address.links:
        for c in customers:
            if l.link_name == c.docname:
                permitted = True
    if permitted:
        address.portal_hide = True
        address.save(ignore_permissions=True)
        frappe.db.commit()
    else:
        raise frappe.PermissionError("You are not allowed to delete this address.")

@frappe.whitelist()
def modify_address(name, address_line1, pincode, city, address_type="Shipping", company_name=None, contact_name=None, address_line2=None, country="Switzerland", phone="", email_id="", commit=True):
    """ Modify an address, by creating a new one and unlinking the existing one """
    create_address(address_line1, pincode, city, address_type, company_name, contact_name, address_line2, country, phone, email_id, commit=True)
    delete_address(name)

@frappe.whitelist()
def get_countries():
    return [c.name for c in frappe.get_all("Country")]