# Copyright (c) 2024, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    # add head column
    columns = [
        {'fieldname': 'account_group', 'label': 'Account Group', 'fieldtype': 'Data', 'width': 200}
    ]
    # add column per company
    companies = frappe.get_all("Company", fields=['name', 'abbr'])
    for c in companies:
        columns.append({
            'fieldname': '{0}'.format(c['abbr']),
            'label': c['abbr'],
            'fieldtype': 'Currency',
            'width': 120
        })
    
    columns.append({
        'fieldname': 'total',
        'label': 'Total',
        'fieldtype': 'Currency',
        'width': 120
    })
    
    return columns
    
def get_data(filters=None):
    data = []
    
    # fetch all account groups
    node_account_groups = frappe.db.sql("""
        SELECT `name`, `is_group`, `level`
        FROM `tabIC Account Group`
        WHERE
            `reporting_type` IN ("Asset", "Liability", "Equity")
            AND (`parent_group` IS NULL OR `parent_group` = "")
        ORDER BY `title` ASC;
        """, as_dict=True)
    
    # build group tree
    account_group_tree = []
    for node in node_account_groups:
        account_group_tree.append(recurse_account_group(node, filters))
    
    # expand tree into a list
    data = expand_node(data, account_group_tree)
    
    # add totals per row
    companies = frappe.get_all("Company", fields=['name', 'abbr'])
    for d in data:
        row_total = 0
        for c in companies:
            row_total += flt(d.get('{0}'.format(c['abbr'])))
        d['total'] = row_total
    
    return data

def expand_node(data, children):
    for d in children:
        _data = {
            'account_group': d['name'],
            'indent': d['level']
        }
        
        for k,v in d.items():
            if k not in ['name', 'is_group', 'level', 'children']:
                _data[k] = v
                        
        data.append(_data)
        
        if 'children' in d:
            data = expand_node(data, d['children'])
    return data
        
def recurse_account_group(node, filters):
    account_group = {
        'name': node['name'], 
        'is_group': node['is_group'],
        'level': node['level']
    }
    
    if node['is_group']:
        account_group['children'] = []
        children = frappe.get_all(
            "IC Account Group", 
            filters={'parent_group': node['name']}, 
            fields=['name', 'is_group', 'level'],
            order_by='title ASC'
        )
        for child in children:
            _child = recurse_account_group(child, filters)
            account_group['children'].append(_child)
            for k,v in _child.items():
                if k not in ['name', 'is_group', 'level', 'children']:
                    if k not in account_group:
                        account_group[k] = (v or 0)
                    else:
                        account_group[k] += (v or 0)
            
    else:
        account_group.update(get_balance_for_account_group(node['name'], filters))
    
    return account_group
        
def get_balance_for_account_group(account_group, filters):
    group_doc = frappe.get_doc("IC Account Group", account_group)
    group_balances = {}
    for account in group_doc.accounts:
        if account.abbr not in group_balances:
            group_balances[account.abbr] = 0
        _balance = get_balance(account.account, filters.get('to_date'))
        if account.currency == "GBP":
            _balance = _balance * filters.get('gbp_exchange_rate')
        elif account.currency == "EUR":
            _balance = _balance * filters.get('eur_exchange_rate')
        group_balances[account.abbr] += _balance
    
    return group_balances
    
def get_balance(account, to_date):
    balance = frappe.db.sql("""
        SELECT IFNULL(SUM(`debit`), 0) - IFNULL(SUM(`credit`), 0) AS `balance`
        FROM `tabGL Entry`
        WHERE
            `account` = "{account}"
            AND `posting_date` <= "{to_date}"
        ;""".format(account=account, to_date=to_date), as_dict=True)
    if len(balance) > 0:
        return balance[0]['balance']
    else:
        return 0
        
