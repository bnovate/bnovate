""" AI features, running on the Google Gemini API.

Configuration is in bNovate Settings: API key, model, the system instructions of each use case, and a glossary that is
appended to all of them.

Layers:
 - call_model() is the only function that knows about the Gemini API. Changing model family or provider should only
   require changes there, plus matching fields in bNovate Settings.
 - generate_json() sends a system instruction and a JSON payload, and returns the JSON the model answered with.
 - Use cases (translate, generate_cover_letter) combine the system instructions from the settings, which describe the task,
   with a hard-coded description of the output format, which the code relies on to parse the answer.

Javascript helpers are in public/js/ai.js.
"""

import html
import json
import os
import re
import time
from urllib.parse import quote

import frappe
import requests
from frappe import _
from frappe.utils import cint, fmt_money
from frappe.utils.html_utils import sanitize_html

from bnovate.bnovate.doctype.sales_proposal.sales_proposal import COST_COLUMNS, get_cost_column_titles, get_cost_groups, get_key_products, render_cost_table

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TIMEOUT = 90  # seconds

# The API answers 503 when the model is overloaded ("spikes in demand"), which usually passes within seconds.
# Retry a few times, then move on to the fallback model from the settings, if there is one.
RETRY_STATUSES = (500, 502, 503, 504)
ATTEMPTS_PER_MODEL = 3
RETRY_DELAYS = (2, 5)  # seconds to wait before the 2nd and the 3rd attempt

# Output formats. These are not configurable, our code depends on them.
TRANSLATE_OUTPUT_FORMAT = """\
# Input and output format
The user message is a JSON object: {"source_language": ..., "target_language": ..., "content": ...}.
`content` is a string, or a list or object (possibly nested) containing strings.

Answer with a single JSON object of the form {"content": ...} and nothing else: no markdown, no code fences, no comments.
The value of `content` in your answer must have exactly the same structure as `content` in the input: same type, same keys,
same number of items in the same order. Only the text of the strings is translated. Strings that are empty, and values
that are not strings, are returned unchanged.
"""

COVER_LETTER_OUTPUT_FORMAT = """\
# Input and output format
The user message is a JSON object with the keys `needs_identified`, `solution_proposed` and `benefits_expected` (notes of
our sales team: what the customer needs, what we propose, and what the customer will gain), `language` (language of the
letter, may be absent), `customer` (recipient: company, contact, billing address), `sender` (our company and sales
contact), `attached_quotations` (the quotations that go with the letter, may be absent) and `attached_appendices` (the
titles of the documents, such as data sheets, that follow the quotations as appendices, may be absent). Keys that have no
value are left out. A quotation that has a `variant_title` is one of several options (variants) that are described on the
pages that follow the letter.

Answer with a single JSON object of the form {"cover_letter": "..."} and nothing else: no markdown, no code fences, no comments.
`cover_letter` is the body of the letter as HTML. Use only <p> for paragraphs, <br> for line breaks inside a paragraph,
<strong> and <em> for emphasis, and <ul>, <ol> and <li> for lists. No other tags, no attributes, no styles.
"""


VARIANTS_OUTPUT_FORMAT = """\
# Input and output format
The user message is a JSON object with the keys `needs_identified`, `solution_proposed` and `benefits_expected` (notes of
our sales team: what the customer needs, what we propose, and what the customer will gain), `language` (language of the
text, may be absent), `customer` (company) and `variants`. `variants` is a list with one entry for each option of the
proposal: {"quotation": number, "key_products": [{"item_code": ..., "item_name": ..., "description": ...}]}. The
descriptions of the key products are in English: use them as information, they are translated separately. Keys that
have no value are left out.

Answer with a single JSON object of the form
{"variants": [{"quotation": "...", "title": "...", "products": "...", "benefits": "..."}]}
and nothing else: no markdown, no code fences, no comments. Give one entry for each variant of the input, in the same
order, with the same `quotation`. `title`, `products` and `benefits` are plain text: no HTML, no markdown.
"""


COST_SIMULATION_OUTPUT_FORMAT = """\
# Input and output format
The user message is a JSON object with `language` (language of the text), `currency`, `column_titles` (the names of the two
columns of the table, `initial` and `running`), `rows` and `totals`. Each row describes the lines of one
section of a quotation that have the same expense category: {"group_id": number, "group": title of the section (may be
absent), "customer_expense_category": "CAPEX", "OPEX, at purchase" or "OPEX, later", "item_names": [...], "total":
amount}. Rows that have the same `group_id` belong to the same line of the table. `totals` are the totals of the two columns
(`initial` and `running`), already formatted with the currency: quote them as they are.

Answer with a single JSON object of the form
{"descriptions": [{"group_id": 1, "description": "..."}], "explanation": "..."}
and nothing else: no markdown, no code fences, no comments. Give one description for each `group_id` of the input. The
descriptions and the explanation are plain text: no HTML, no markdown. The table itself and all its amounts are made by our
code from the input: you do not write them.
"""


# ------------------------------------------------------------------ Gemini

def get_settings():
    """ Return the AI configuration from bNovate Settings. """
    settings = frappe.get_single("bNovate Settings")
    api_key = settings.get_password("gemini_api_key", raise_exception=False)
    model = (settings.gemini_model or "").strip()
    if model.startswith("models/"):
        model = model[len("models/"):]

    if not api_key or not model:
        frappe.throw(_("Please set the Gemini API Key and Gemini Model in bNovate Settings."))
    if not re.fullmatch(r"[A-Za-z0-9._-]+", model):
        frappe.throw(_("Invalid Gemini Model: {0}").format(model))

    fallback_model = (settings.gemini_fallback_model or "").strip()
    if fallback_model.startswith("models/"):
        fallback_model = fallback_model[len("models/"):]
    if fallback_model and not re.fullmatch(r"[A-Za-z0-9._-]+", fallback_model):
        frappe.throw(_("Invalid Gemini Fallback Model: {0}").format(fallback_model))

    return frappe._dict(
        api_key=api_key,
        model=model,
        fallback_model=fallback_model if fallback_model != model else "",
        cover_letter_system_instructions=(settings.cover_letter_system_instructions or "").strip(),
        variants_system_instructions=(settings.variants_system_instructions or "").strip(),
        cost_simulation_system_instructions=(settings.cost_simulation_system_instructions or "").strip(),
        translation_system_instructions=(settings.translation_system_instructions or "").strip(),
    )


class _ModelUnavailable(Exception):
    """ The model is overloaded or out of quota: worth trying again later, or with another model. """


def _post_with_retries(api_key, model, body):
    """ POST the request to the model, retrying when it is overloaded. Return the response, whatever its status, except
    when the model is unavailable: then raise _ModelUnavailable. """
    reason = ""
    for attempt in range(ATTEMPTS_PER_MODEL):
        if attempt:
            time.sleep(RETRY_DELAYS[attempt - 1])
        try:
            response = requests.post(
                GEMINI_URL.format(model=quote(model, safe="")),
                headers={"x-goog-api-key": api_key},
                json=body,
                timeout=TIMEOUT,
            )
        except requests.Timeout:
            # Already waited TIMEOUT seconds, do not make the user wait for that again
            frappe.throw(_("The Gemini API did not answer in time, please try again."))
        except requests.ConnectionError as e:
            reason = e.__class__.__name__
            continue
        except requests.RequestException as e:
            frappe.throw(_("Could not reach the Gemini API: {0}").format(e.__class__.__name__))

        if response.status_code == 429:
            # Out of quota or rate limited: waiting a few seconds will not help, another model has its own quota.
            raise _ModelUnavailable(_error_message(response))
        if response.status_code in RETRY_STATUSES:
            reason = _error_message(response)
            continue
        return response

    raise _ModelUnavailable(reason)


def _error_message(response):
    """ Readable error from a failed API response, with its status code. """
    try:
        message = (response.json().get("error") or {}).get("message")
    except ValueError:
        message = None
    return "{0}: {1}".format(response.status_code, message or response.reason)


def call_model(system_instruction, content, json_output=True):
    """ Send one request to the model, return the text of its answer.

    Args:
        system_instruction (str): standing instructions, sent before the content
        content (str): the content to work on
        json_output (bool): ask for a JSON answer
    """
    settings = get_settings()

    body = {
        "system_instruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"role": "user", "parts": [{"text": content}]}],
    }
    if json_output:
        body["generationConfig"] = {"responseMimeType": "application/json"}

    models = [settings.model] + ([settings.fallback_model] if settings.fallback_model else [])
    for index, model in enumerate(models):
        try:
            response = _post_with_retries(settings.api_key, model, body)
            break
        except _ModelUnavailable as e:
            if index == len(models) - 1:
                frappe.throw(_("Gemini is overloaded, please try again in a minute. ({0})").format(e))

    try:
        data = response.json()
    except ValueError:
        data = {}

    if response.status_code != 200:
        message = (data.get("error") or {}).get("message") or response.reason
        frappe.throw(_("Gemini API error ({0}): {1}").format(response.status_code, message))

    blocked = (data.get("promptFeedback") or {}).get("blockReason")
    if blocked:
        frappe.throw(_("The request was blocked by Gemini: {0}").format(blocked))

    candidates = data.get("candidates") or []
    if not candidates:
        frappe.throw(_("Gemini returned no answer."))

    candidate = candidates[0]
    finish_reason = candidate.get("finishReason")
    if finish_reason not in (None, "STOP"):
        frappe.throw(_("Gemini did not finish its answer: {0}").format(finish_reason))

    parts = (candidate.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    if not text.strip():
        frappe.throw(_("Gemini returned an empty answer."))
    return text


def generate_json(system_instruction, output_format, payload):
    """ Send the payload (anything JSON serializable) with the system instruction and the description of the output
    format. Return the JSON value the model answered with.
    """
    glossary = (frappe.db.get_single_value("bNovate Settings", "ai_glossary") or "").strip()
    system_instruction = "\n\n".join(s for s in (system_instruction, glossary, output_format) if s)
    text = call_model(system_instruction, json.dumps(payload, ensure_ascii=False), json_output=True)

    # JSON mode should return bare JSON, but be forgiving if the model wrapped it in a code fence anyway.
    text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text)
    try:
        return json.loads(text)
    except ValueError:
        frappe.log_error(text, "Gemini returned invalid JSON")
        frappe.throw(_("Gemini did not return valid JSON. Please try again."))


# ------------------------------------------------------------------ Use cases

def _from_client(value):
    """ Lists and objects come through frappe.call as JSON strings. Leave plain strings alone. """
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return value
        if isinstance(parsed, (list, dict)):
            return parsed
    return value


def _same_structure(a, b):
    """ True if both values have the same shape: same types, keys and list lengths. """
    if isinstance(a, dict):
        return isinstance(b, dict) and a.keys() == b.keys() and all(_same_structure(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return isinstance(b, list) and len(a) == len(b) and all(_same_structure(x, y) for x, y in zip(a, b))
    if isinstance(a, str):
        return isinstance(b, str)
    return a == b


@frappe.whitelist()
def translate(texts, target_lang, source_lang="en"):
    """ Translate a string, or a list or object of strings. The result has the same structure as the input.

    Args:
        texts (str, list or dict): text(s) to translate. HTML tags are preserved.
        target_lang (str): target language, e.g. "de" or "French"
        source_lang (str, optional): source language (default "en")
    """
    texts = _from_client(texts)
    settings = get_settings()

    answer = generate_json(
        settings.translation_system_instructions,
        TRANSLATE_OUTPUT_FORMAT,
        {"source_language": source_lang, "target_language": target_lang, "content": texts},
    )

    if not isinstance(answer, dict) or "content" not in answer or not _same_structure(texts, answer["content"]):
        frappe.log_error(json.dumps({"input": texts, "answer": answer}, ensure_ascii=False, indent=1), "Gemini translation does not match the input")
        frappe.throw(_("The translation does not have the same structure as the original. Please try again."))

    return answer["content"]


def _html_to_text(value):
    """ Plain text version of an address block (HTML with <br>s). """
    value = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.I)
    value = html.unescape(re.sub(r"<[^>]+>", "", value))
    return "\n".join(line.strip() for line in value.splitlines() if line.strip())


def _compact(d):
    """ Remove empty values, from a dict and the dicts it contains. """
    result = {}
    for k, v in d.items():
        v = _compact(v) if isinstance(v, dict) else v
        if v:
            result[k] = v
    return result


def _ensure_html(text):
    """ The model is asked for HTML. If it answered with plain text anyway, turn the paragraphs into HTML. """
    if re.search(r"</?(?:p|br|div|ul|ol|li|strong|em|b|i)\b[^>]*>", text, re.I):
        return text
    paragraphs = re.split(r"\n\s*\n", text.strip())
    return "".join("<p>{0}</p>".format("<br>".join(html.escape(line) for line in p.splitlines())) for p in paragraphs)


def _to_editor_html(value):
    """ The Text Editor field of the form writes <div> lines with an empty line between paragraphs, not <p> tags.
    Do the same, so that the letter looks the same before and after it is edited by hand. """
    value = re.sub(r"<p(?:\s[^>]*)?>", "<div>", value).replace("</p>", "</div>")
    return re.sub(r"</div>\s*<div>", "</div><div><br></div><div>", value)


@frappe.whitelist()
def generate_cover_letter(doc):
    """ Write the cover letter of a Sales Proposal from its Proposal Elements. Return the letter as HTML.

    Args:
        doc (dict): the Sales Proposal, as in the form (it may have unsaved changes). Used: needs_identified,
            solution_proposed, benefits_expected, language, customer_name, contact_person, contact_display,
            customer_address, address_display, company, sales_contact, sales_contact_name, and the quotations of the
            Linked Quotations table, and the titles of the Appendices table.
    """
    frappe.has_permission("Sales Proposal", "read", throw=True)
    doc = frappe._dict(_from_client(doc))

    elements = {key: (doc.get(key) or "").strip() for key in ("needs_identified", "solution_proposed", "benefits_expected")}
    if not any(elements.values()):
        frappe.throw(_("Please fill in the Proposal Elements first."))

    settings = get_settings()

    address = frappe.db.get_value("Address", doc.customer_address, ["address_title", "company_name"], as_dict=True) if doc.customer_address else None
    salutation = frappe.db.get_value("Contact", doc.contact_person, "salutation") if doc.contact_person else None

    attached_quotations = []
    for row in doc.get("quotations") or []:
        name = row.get("quotation")
        if name and frappe.db.exists("Quotation", name) and frappe.has_permission("Quotation", "read", doc=name):
            items = frappe.get_all(
                "Quotation Item",
                filters={"parent": name, "parenttype": "Quotation"},
                fields=["item_code", "item_name"],
                order_by="idx asc",
            )
            attached_quotations.append({
                "number": name,
                "title": frappe.db.get_value("Quotation", name, "title"),
                "variant_title": (row.get("variant_title") or "").strip(),
                "items": [{"item_code": item.item_code, "item_name": item.item_name} for item in items],
            })

    appendices = [
        (row.get("title") or "").strip() or os.path.splitext(os.path.basename(row.get("file") or ""))[0]
        for row in doc.get("appendices") or [] if row.get("file")
    ]

    payload = _compact(dict(
        elements,
        language=doc.language,
        customer={
            "company": doc.customer_name,
            "billing_company_name": address and (address.company_name or address.address_title),
            "billing_address": _html_to_text(doc.address_display),
            "contact_name": doc.contact_display,
            "contact_salutation": salutation,
        },
        sender={
            "company": doc.company,
            "sales_contact_name": doc.sales_contact_name,
            "sales_contact_email": doc.sales_contact,
        },
        attached_quotations=attached_quotations,
        attached_appendices=appendices,
    ))

    answer = generate_json(settings.cover_letter_system_instructions, COVER_LETTER_OUTPUT_FORMAT, payload)

    if not isinstance(answer, dict) or not isinstance(answer.get("cover_letter"), str) or not answer["cover_letter"].strip():
        frappe.log_error(json.dumps(answer, ensure_ascii=False, indent=1), "Gemini cover letter does not match the expected format")
        frappe.throw(_("Gemini did not return the cover letter in the expected format. Please try again."))

    return _to_editor_html(sanitize_html(_ensure_html(answer["cover_letter"].strip())))


@frappe.whitelist()
def generate_variants(doc):
    """ Describe the variants of a Sales Proposal: one for each linked quotation that has key products. For each:
    a title, a paragraph on the products, a paragraph on the benefits, written by the model, and the description of each
    key product, which is the commercial description of the item master translated into the language of the proposal.

    Args:
        doc (dict): the Sales Proposal, as in the form (it may have unsaved changes). Used: needs_identified,
            solution_proposed, benefits_expected, language, customer_name, and the quotations of the Linked Quotations table.

    Return {"variants": [{"quotation", "title", "intro", "benefits", "items": [{"item_code", "item_name", "description"}]}],
    "skipped": [quotations without key products]}.
    """
    frappe.has_permission("Sales Proposal", "read", throw=True)
    doc = frappe._dict(_from_client(doc))

    elements = {key: (doc.get(key) or "").strip() for key in ("needs_identified", "solution_proposed", "benefits_expected")}
    if not any(elements.values()):
        frappe.throw(_("Please fill in the Proposal Elements first."))

    settings = get_settings()

    variants, skipped = [], []
    for row in doc.get("quotations") or []:
        name = row.get("quotation")
        if not name or name in [v["quotation"] for v in variants] or not frappe.db.exists("Quotation", name) \
                or not frappe.has_permission("Quotation", "read", doc=name):
            continue
        products = get_key_products(name)
        if products:
            variants.append({"quotation": name, "key_products": products})
        else:
            skipped.append(name)

    if not variants:
        frappe.throw(_("None of the linked quotations has an item with a commercial description."))

    payload = _compact(dict(elements, language=doc.language, customer={"company": doc.customer_name}, variants=[
        {"quotation": v["quotation"], "key_products": [
            {"item_code": p.item_code, "item_name": p.item_name, "description": p.description} for p in v["key_products"]]}
        for v in variants
    ]))

    answer = generate_json(settings.variants_system_instructions, VARIANTS_OUTPUT_FORMAT, payload)

    answered = {}
    if isinstance(answer, dict) and isinstance(answer.get("variants"), list):
        answered = {a.get("quotation"): a for a in answer["variants"] if isinstance(a, dict)}

    def text(value):
        return value.strip() if isinstance(value, str) else ""

    result = []
    for variant in variants:
        a = answered.get(variant["quotation"])
        if not a or not (text(a.get("title")) and text(a.get("products")) and text(a.get("benefits"))):
            frappe.log_error(json.dumps(answer, ensure_ascii=False, indent=1), "Gemini variants do not match the expected format")
            frappe.throw(_("Gemini did not return the variants in the expected format. Please try again."))

        result.append({
            "quotation": variant["quotation"],
            "title": text(a["title"]),
            "intro": text(a["products"]),
            "benefits": text(a["benefits"]),
            "items": [
                {
                    "item_code": p.item_code,
                    "item_name": p.item_name,
                    "description": p.description,
                    "image": p.image,
                }
                for p in variant["key_products"]
            ],
        })

    # The descriptions come from the item masters, in English: translate them as they are.
    language = (doc.language or "").strip()
    if language and language.lower() != "en":
        descriptions = {p.item_code: p.description for v in variants for p in v["key_products"]}
        translated = translate(descriptions, language)
        for variant in result:
            for item in variant["items"]:
                item["description"] = translated[item["item_code"]]

    return {"variants": result, "skipped": skipped}


@frappe.whitelist()
def generate_cost_simulation(quotation, language=None, strict=1):
    """ Cost simulation of a quotation: a table that shows, for each section of the quotation, the initial purchase and
    the running costs as quoted, with the explanation written by the AI.

    The sums are calculated by get_cost_groups() and the table is built by render_cost_table(): the AI writes the description of
    each line and an explanation, and never makes or restates an amount of the table.

    Return {"html": the simulation, "unclassified": [lines that have an amount but no expense category, left out of the table]}.
    A quotation without any expense category is an error, unless strict is off (when several quotations are done at once): the
    answer is then {"html": None, "empty": 1, "unclassified": [...]}.
    """
    frappe.has_permission("Quotation", "read", doc=quotation, throw=True)

    groups = get_cost_groups(quotation)
    if not groups["rows"]:
        if cint(strict):
            frappe.throw(_("None of the lines of the quotation has a Customer Expense Category (CAPEX or OPEX)."))
        return {"html": None, "empty": 1, "unclassified": groups["unclassified"]}

    settings = get_settings()

    totals = dict.fromkeys(COST_COLUMNS, 0.0)
    for row in groups["rows"]:
        for column, categories in COST_COLUMNS.items():
            if row["customer_expense_category"] in categories:
                totals[column] += row["total"]
    titles = get_cost_column_titles(language)

    payload = _compact(dict(
        language=language, currency=groups["currency"], column_titles=titles,
        rows=[dict(row) for row in groups["rows"]],
        totals={category: fmt_money(total, currency=groups["currency"]) for category, total in totals.items()},
    ))
    answer = generate_json(settings.cost_simulation_system_instructions, COST_SIMULATION_OUTPUT_FORMAT, payload)

    wanted = {row["group_id"] for row in groups["rows"]}
    descriptions = {}
    if isinstance(answer, dict) and isinstance(answer.get("descriptions"), list):
        for d in answer["descriptions"]:
            if isinstance(d, dict) and isinstance(d.get("description"), str) and d["description"].strip():
                try:
                    descriptions[int(d.get("group_id"))] = d["description"].strip()
                except (TypeError, ValueError):
                    pass
    if not wanted <= set(descriptions):
        # The table does not depend on it: a line without description from the model is described by its section and items.
        frappe.log_error(json.dumps(answer, ensure_ascii=False, indent=1), "Gemini cost simulation: descriptions are missing")

    explanation = answer.get("explanation") if isinstance(answer, dict) and isinstance(answer.get("explanation"), str) else ""
    return {"html": render_cost_table(groups, descriptions, explanation, language), "unclassified": groups["unclassified"]}
