from __future__ import unicode_literals
from frappe import _

def get_data():
	return {
		'fieldname': 'subscription',
		'internal_links': {
			'Quotation': ['items', 'prevdoc_docname']
		},
		'transactions': [
			{
				'label': _('Sales'),
				'items': ['Quotation', 'Sales Invoice']
			},
			# {
			# 	'label': _('Packages'),
			# 	'items': ['Connectivity Package']
			# },
		]
	}