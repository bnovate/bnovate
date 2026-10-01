# -*- coding: utf-8 -*-
# Copyright (c) 2026, bnovate, libracore and contributors
#
# Warehouse Wars: a little point-and-shoot easter egg for a barcode-reader.
# Enemies are labelled with real Serial No values from the database - the
# QR code on each enemy IS that serial, so "shooting" one means scanning it
# for real with a handheld reader (which behaves as a keyboard, typing the
# code followed by Enter/Tab - see warehouse_wars.js for the capture side).
from __future__ import unicode_literals
import frappe


@frappe.whitelist()
def get_enemies(count=16):
    """ A batch of real Serial No names to use as enemy codes for one level.

    Picked at random each time so repeat playthroughs don't always face the
    same squad. Uses frappe.get_list (not a raw query) so this only ever
    returns serials the current user actually has permission to see.
    """
    count = int(count)
    rows = frappe.get_list(
        "Serial No",
        fields=["name"],
        order_by="RAND()",
        limit_page_length=count,
    )
    return [row.name for row in rows]
