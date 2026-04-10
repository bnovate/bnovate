# -*- coding: utf-8 -*-
# Copyright (c) 2024-2026, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class ICAccountGroup(Document):
    def before_save(self):
        if self.parent_group:
            parent_level = frappe.get_value("IC Account Group", self.parent_group, "level")
            self.level = parent_level + 1
        else:
            self.level = 0
            
        return
