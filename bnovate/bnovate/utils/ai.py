""" AI features, running on the Google Gemini API.

Configuration is in bNovate Settings: API key, model, and the system instructions of each use case.

Layers:
 - call_model() is the only function that knows about the Gemini API. Changing model family or provider should only
   require changes there, plus matching fields in bNovate Settings.
 - generate_json() sends a system instruction and a JSON payload, and returns the JSON the model answered with.
 - Use cases (translate, enhance_qtn_blurb) combine the system instructions from the settings, which describe the task,
   with a hard-coded description of the output format, which the code relies on to parse the answer.

Javascript helpers are in public/js/ai.js.
"""

import html
import json
import re
from urllib.parse import quote

import frappe
import requests
from frappe import _

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TIMEOUT = 90  # seconds

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

QTN_BLURB_OUTPUT_FORMAT = """\
# Input and output format
The user message is a JSON object with the keys `draft` (the text to improve), `language` (language of the letter, may be
absent), `customer` (recipient: company, contact, billing address) and `sender` (our company and sales contact).
Keys that have no value are left out.

Answer with a single JSON object of the form {"blurb": "..."} and nothing else: no markdown, no code fences, no comments.
`blurb` is the improved text as plain text. Separate paragraphs with a blank line (two newline characters).
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

    return frappe._dict(
        api_key=api_key,
        model=model,
        quotation_blurb_system_instructions=(settings.quotation_blurb_system_instructions or "").strip(),
        translation_system_instructions=(settings.translation_system_instructions or "").strip(),
    )


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

    try:
        response = requests.post(
            GEMINI_URL.format(model=quote(settings.model, safe="")),
            headers={"x-goog-api-key": settings.api_key},
            json=body,
            timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        frappe.throw(_("Could not reach the Gemini API: {0}").format(e.__class__.__name__))

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
    system_instruction = "\n\n".join(s for s in (system_instruction, output_format) if s)
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


@frappe.whitelist()
def enhance_qtn_blurb(doc):
    """ Return an improved version of the blurb (the cover letter text) of a Quotation.

    Args:
        doc (dict): the Quotation, as in the form (it may have unsaved changes). Used: blurb, language, customer_name,
            contact_person, contact_display, customer_address, address_display, company, sales_contact,
            sales_contact_name.
    """
    frappe.has_permission("Quotation", "read", throw=True)
    doc = frappe._dict(_from_client(doc))

    if not (doc.blurb or "").strip():
        frappe.throw(_("Please write a few notes in the Blurb first."))

    settings = get_settings()

    address = frappe.db.get_value("Address", doc.customer_address, ["address_title", "company_name"], as_dict=True) if doc.customer_address else None
    salutation = frappe.db.get_value("Contact", doc.contact_person, "salutation") if doc.contact_person else None

    payload = _compact({
        "draft": doc.blurb,
        "language": doc.language,
        "customer": {
            "company": doc.customer_name,
            "billing_company_name": address and (address.company_name or address.address_title),
            "billing_address": _html_to_text(doc.address_display),
            "contact_name": doc.contact_display,
            "contact_salutation": salutation,
        },
        "sender": {
            "company": doc.company,
            "sales_contact_name": doc.sales_contact_name,
            "sales_contact_email": doc.sales_contact,
        },
    })

    answer = generate_json(settings.quotation_blurb_system_instructions, QTN_BLURB_OUTPUT_FORMAT, payload)

    if not isinstance(answer, dict) or not isinstance(answer.get("blurb"), str) or not answer["blurb"].strip():
        frappe.log_error(json.dumps(answer, ensure_ascii=False, indent=1), "Gemini blurb does not match the expected format")
        frappe.throw(_("Gemini did not return the blurb in the expected format. Please try again."))

    return answer["blurb"].strip()
