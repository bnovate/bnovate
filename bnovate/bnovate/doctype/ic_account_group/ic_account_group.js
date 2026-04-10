// Copyright (c) 2024, libracore and contributors
// For license information, please see license.txt

// filters: define globally
cur_frm.fields_dict.accounts.grid.get_field('account').get_query = function(frm, cdt, cdn) {
    var d = locals[cdt][cdn];     
    return {
        'filters': {
            'company': d.company ,
            'is_group': 0
        }                       
    }
}

cur_frm.fields_dict.parent_group.get_query = function(doc) {
         return {
             filters: {
                 "is_group": 1
             }
         }
    }
    
frappe.ui.form.on('IC Account Group', {
    refresh: function(frm) {

    }
});
