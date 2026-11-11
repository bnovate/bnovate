# (C) 2026, bNovate
#
# Quotation PDFs with a branded cover page.
#
# - The cover is rendered from templates/includes/bn_quotation_cover.html by wkhtmltopdf, full bleed (no margins, no
#   letterhead), and merged in front of the normal print output. "Page X of Y" of the body therefore excludes the cover.
# - The big title of the cover is the title of the quotation (ERPNext sets it to the customer name by default), shrunk
#   and wrapped to fit. The cover never shows the quotation number or a subtitle.
# - Fonts and images are embedded in the HTML as data URIs: Frappe's PDF generation does not allow local files.
#
# Called from public/js/doctype_includes/quotation.js through download_quotation_pdf().

import base64
import io
import os
from functools import lru_cache

import frappe
import pdfkit
from frappe import _
from frappe.utils import formatdate
from frappe.utils.pdf import get_file_data_from_writer
from frappe.www.printview import get_print_format_doc
from PIL import ImageFont
from PyPDF2 import PdfFileReader, PdfFileWriter

# kind -> print format of the body, and small heading of the cover
KINDS = {
    "quotation": {"print_format": "Quotation", "kicker": "Quotation"},
    "price_list": {"print_format": "Price List", "kicker": "Price List"},
}

CONTACT = ["+41 21 552 14 21", "sales@bnovate.com", "www.bnovate.com"]
DATE_FORMAT = "dd-mm-yyyy"

FONTS = ["Barlow-Regular", "Barlow-Medium", "Barlow-SemiBold", "Barlow-Bold"]

# Box of the title on the cover, in pt, and the font sizes tried from large to small. Keep in sync with .title in the template.
TITLE_FONT = "Barlow-SemiBold"
TITLE_WIDTH = 480
TITLE_HEIGHT = 126
TITLE_SIZES = range(50, 19, -2)
TITLE_LINE_HEIGHT = 1.1


@lru_cache(maxsize=None)
def _embedded(*path):
    """ Base64 of a file of the app's public folder """
    with open(frappe.get_app_path("bnovate", "public", *path), "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


@lru_cache(maxsize=None)
def _title_font():
    return ImageFont.truetype(frappe.get_app_path("bnovate", "public", "fonts", TITLE_FONT + ".ttf"), 100)


def _wrap(text, size):
    """ Greedy word wrap of text for the title at this font size (pt). Return the lines and the width of the widest. """
    font, scale = _title_font(), size / 100.0
    lines, line = [], ""
    for word in text.split():
        candidate = (line + " " + word).strip()
        if not line or font.getlength(candidate) * scale <= TITLE_WIDTH:
            line = candidate
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines, max([font.getlength(l) * scale for l in lines] or [0])


def fit_title(title):
    """ Lines and font size (pt) to print the title in its box on the cover: the largest size at which it fits. """
    title = " ".join((title or "").split())
    for size in TITLE_SIZES:
        lines, width = _wrap(title, size)
        if width <= TITLE_WIDTH and len(lines) * size * TITLE_LINE_HEIGHT <= TITLE_HEIGHT:
            return lines, size

    # Does not fit even at the smallest size: cut it.
    size = TITLE_SIZES[-1]
    lines, _width = _wrap(title, size)
    max_lines = int(TITLE_HEIGHT // (size * TITLE_LINE_HEIGHT))
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] += "…"
    return lines, size


def get_cover_pdf(kind, title, valid_from, valid_till, currency):
    """ Return the cover page as PDF bytes.

    kind: key of KINDS. title: big title. valid_from and valid_till are dates, formatted dd-mm-yyyy.
    """
    cover = KINDS[kind]
    title_lines, title_size = fit_title(title)
    html = frappe.render_template("templates/includes/bn_quotation_cover.html", {
        "kicker": _(cover["kicker"]),
        "title_lines": title_lines,
        "title_size": title_size,
        "title_line_height": round(title_size * TITLE_LINE_HEIGHT, 2),
        "rows": [
            (_("Valid From"), formatdate(valid_from, DATE_FORMAT) if valid_from else ""),
            (_("Valid Till"), formatdate(valid_till, DATE_FORMAT) if valid_till else ""),
            (_("Currency"), currency or ""),
        ],
        "contact": CONTACT,
        "fonts": {name: _embedded("fonts", name + ".ttf") for name in FONTS},
        "images": {name: _embedded("img", "cover", name + ".png") for name in ("cover_bg", "logo_white")},
    })

    return pdfkit.from_string(html, False, options={
        "page-size": "A4",
        "margin-top": "0", "margin-bottom": "0", "margin-left": "0", "margin-right": "0",
        "disable-smart-shrinking": "",
        "print-media-type": "",
        "background": "",
        "images": "",
        "quiet": "",
        "encoding": "UTF-8",
        "disable-javascript": "",
        "disable-local-file-access": "",
    })


def get_quotation_pdf(name, kind):
    """ PDF of a Quotation, with the cover of the given kind in front.

    The body is the print format of that kind, rendered like the print preview does: in the default language
    of the print format, else the language of the quotation, else the user's.
    """
    cover = KINDS[kind]
    doc = frappe.get_doc("Quotation", name)
    doc.check_permission("read")

    print_format = get_print_format_doc(cover["print_format"], meta=frappe.get_meta("Quotation"))
    lang = (print_format and print_format.default_print_language) or doc.get("language") or frappe.local.lang
    previous_lang = frappe.local.lang
    try:
        frappe.local.lang = lang
        body = frappe.get_print("Quotation", name, print_format=cover["print_format"], as_pdf=True)

        front = get_cover_pdf(kind, doc.title or doc.customer_name, doc.transaction_date, doc.valid_till, doc.currency)
    finally:
        frappe.local.lang = previous_lang

    writer = PdfFileWriter()
    writer.appendPagesFromReader(PdfFileReader(io.BytesIO(front)))
    writer.appendPagesFromReader(PdfFileReader(io.BytesIO(body)))
    return get_file_data_from_writer(writer)


@frappe.whitelist()
def download_quotation_pdf(name, kind="quotation"):
    """ Download a Quotation as PDF with a cover page. kind is "quotation" or "price_list". """
    if kind not in KINDS:
        frappe.throw(_("Unknown kind: {0}").format(kind))

    frappe.local.response.filename = "{0}.pdf".format(name)
    frappe.local.response.filecontent = get_quotation_pdf(name, kind)
    frappe.local.response.type = "pdf"
