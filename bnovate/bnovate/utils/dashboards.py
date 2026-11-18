# (C) 2023, bNovate
#
# Custom dashboard code for standard doctypes.

from __future__ import unicode_literals
import frappe
from frappe import _

def get_serial_no_dashboard_data(data):
    return frappe._dict({
        'fieldname': 'serial_no',
        'non_standard_fieldnames': {
            'Connectivity Package': 'instrument_serial_no',
        },
        'transactions': [
            {
                'label': _('Add-ons'),
                'items': ['License Key', 'Subscription Contract', 'Connectivity Package'],
            }, {
                'label': _('Storage'),
                'items': ['Storage Location'],
            }, {
                'label': _('Service'),
                'items': ['Service Report'],
            }
        ],
    })


def get_sales_order_dashboard_data(data):
    data.internal_links['Refill Request'] = ['items', 'refill_request']
    data.internal_links['Service Report'] = ['items', 'service_report']

    return data


def get_quotation_dashboard_data(data):
    # Service Reports point to the quotation through their own field. The transactions are added in quotation.js
    data.non_standard_fieldnames['Service Report'] = 'quotation'

    # Sales Proposals list quotations in a child table, so the standard count can not find them. Declared as an internal
    # link so that the standard code leaves the badge alone; quotation.js fills it in (dashboard_update).
    data.internal_links = data.internal_links or {}
    data.internal_links['Sales Proposal'] = ['quotations', 'quotation']

    return data
