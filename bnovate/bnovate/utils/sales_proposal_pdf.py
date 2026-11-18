# (C) 2026, bNovate
#
# PDF of a Sales Proposal: a branded cover page, the cover letter, the variants (if they are described), then the appendices: a branded "Appendix" page,
# the linked quotations, and the PDFs attached to the proposal.
#
# - The cover and the appendix page are rendered from templates/includes/bn_sales_proposal_cover.html by wkhtmltopdf, full bleed (no margins,
#   no letterhead). The letter is the "Sales Proposal" print format, and each quotation is printed with the "Quotation"
#   print format. The PDFs are merged, so "Page X of Y" of each part only counts its own pages.
# - The big title of the cover is the title of the proposal, shrunk and wrapped to fit.
# - Fonts and images are embedded in the HTML as data URIs: Frappe's PDF generation does not allow local files.
#
# Called from sales_proposal.js through download_sales_proposal_pdf().

import base64
import io
from functools import lru_cache

import frappe
import pdfkit
from frappe import _
from frappe.utils import formatdate, strip_html
from frappe.utils.pdf import get_file_data_from_writer
from frappe.www.printview import get_print_format_doc
from bnovate.bnovate.doctype.sales_proposal.sales_proposal import get_pdf_attachments
from PIL import ImageFont
from PyPDF2 import PdfFileReader, PdfFileWriter

LETTER_PRINT_FORMAT = "Sales Proposal"
VARIANTS_PRINT_FORMAT = "Sales Proposal Variants"
QUOTATION_PRINT_FORMAT = "Quotation"

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


def get_branded_page_pdf(kicker, title, rows=(), minimal=False):
    """ Return a full page with the bNovate branding as PDF bytes: the cover, or the page that introduces the appendices.

    kicker: small text above the title. title: big title. rows: (label, value) pairs under the title.
    minimal: no logo and contact details, just a gradient at the bottom.
    """
    title_lines, title_size = fit_title(title)
    html = frappe.render_template("templates/includes/bn_sales_proposal_cover.html", {
        "kicker": kicker,
        "title_lines": title_lines,
        "title_size": title_size,
        "title_line_height": round(title_size * TITLE_LINE_HEIGHT, 2),
        "rows": rows,
        "minimal": minimal,
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


def get_cover_pdf(title, date):
    """ Return the cover page as PDF bytes.

    title: big title. date: date of the proposal.
    """
    return get_branded_page_pdf(_("Sales Proposal"), title, [(_("Date"), formatdate(date, DATE_FORMAT) if date else "")])


def get_appendix_pdf():
    """ Return the page that separates the cover letter from the appendices (quotations and attached PDFs), as PDF bytes. """
    return get_branded_page_pdf(_("Sales Proposal"), _("Appendix"), minimal=True)


def get_appendices(name):
    """ The PDFs attached to a Sales Proposal, as a list of PdfFileReader. """
    readers = []
    for attachment in get_pdf_attachments(name):
        try:
            reader = PdfFileReader(io.BytesIO(frappe.get_doc("File", attachment.name).get_content()), strict=False)
            if reader.isEncrypted:
                reader.decrypt("")
            reader.getNumPages()
        except Exception:
            frappe.throw(_("The attached file {0} could not be read as a PDF.").format(attachment.file_name))
        readers.append(reader)
    return readers


def get_print_pdf(doctype, name, print_format, lang=None):
    """ PDF of a document with a print format, rendered like the print preview does: in the default language of the
    print format, else the given language, else the language of the document, else the user's.
    """
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("read")

    print_format_doc = get_print_format_doc(print_format, meta=frappe.get_meta(doctype))
    lang = (print_format_doc and print_format_doc.default_print_language) or lang or doc.get("language") or frappe.local.lang

    previous_lang = frappe.local.lang
    try:
        frappe.local.lang = lang
        return frappe.get_print(doctype, name, print_format=print_format, as_pdf=True)
    finally:
        frappe.local.lang = previous_lang


def get_sales_proposal_pdf(name):
    """ PDF of a Sales Proposal: cover, cover letter (if there is one), the variants (if they are described), then the appendices (if there are any): the page that
    introduces them, the linked quotations in the order of the table, and the PDFs attached to the proposal. """
    doc = frappe.get_doc("Sales Proposal", name)
    doc.check_permission("read")

    appendices = get_appendices(name)
    parts = []

    previous_lang = frappe.local.lang
    try:
        frappe.local.lang = doc.language or previous_lang
        parts.append(get_cover_pdf(doc.title or doc.customer_name, doc.transaction_date))
        appendix_page = get_appendix_pdf() if (appendices or doc.quotations) else None
    finally:
        frappe.local.lang = previous_lang

    if strip_html(doc.cover_letter or "").strip():
        parts.append(get_print_pdf("Sales Proposal", name, LETTER_PRINT_FORMAT, doc.language))

    if any(row.variant_title for row in doc.quotations):
        parts.append(get_print_pdf("Sales Proposal", name, VARIANTS_PRINT_FORMAT, doc.language))

    if appendix_page:
        parts.append(appendix_page)

    for row in doc.quotations:
        parts.append(get_print_pdf("Quotation", row.quotation, QUOTATION_PRINT_FORMAT, doc.language))

    readers = [PdfFileReader(io.BytesIO(part)) for part in parts]
    readers.extend(appendices)

    writer = PdfFileWriter()
    for reader in readers:
        writer.appendPagesFromReader(reader)
    return get_file_data_from_writer(writer)


@frappe.whitelist()
def download_sales_proposal_pdf(name):
    """ Download a Sales Proposal as PDF. """
    frappe.local.response.filename = "{0}.pdf".format(name)
    frappe.local.response.filecontent = get_sales_proposal_pdf(name)
    frappe.local.response.type = "pdf"
