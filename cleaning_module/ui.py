import json
import re
from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


DATA_DIR = Path(__file__).resolve().parent / "data"
JSON_FILE = DATA_DIR / "quotes.json"
EXCEL_FILE = DATA_DIR / "quotes.xlsx"

COLUMNS = [
    "Reference No",
    "Created At",
    "Customer Name",
    "POL",
    "POD",
    "Cargo Name",
    "Rate Type",
    "Currency",
    "Rental Amount",
    "Free Days From",
    "Free Days To",
    "Thereafter Rate / Day",
]

FORM_FIELDS = {
    "customer_name": "",
    "pol": "",
    "pod": "",
    "cargo_name": "",
    "rate_type": "Pure Rental",
    "currency": "USD",
    "rental_amount": "",
    "free_days_from": "",
    "free_days_to": "",
    "thereafter_rate": "",
    "local_charges": "Additional",
    "remarks": "",
}


def _ensure_storage():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_quotes():
    _ensure_storage()
    if not JSON_FILE.exists():
        return []
    with JSON_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def _save_quotes_json(quotes):
    _ensure_storage()
    with JSON_FILE.open("w", encoding="utf-8") as file:
        json.dump(quotes, file, indent=2, ensure_ascii=False)


def _get_base_reference(reference_no):
    return re.sub(r"-R\d+$", "", reference_no or "")


def _get_revision_number(reference_no):
    match = re.search(r"-R(\d+)$", reference_no or "")
    return int(match.group(1)) if match else 0


def _generate_reference_number(existing_quotes):
    date_code = datetime.now().strftime("%y%m%d")
    prefix = f"OLR{date_code}"
    root_refs = []
    for quote in existing_quotes:
        ref = quote.get("Reference No", "")
        if ref.startswith(prefix) and "-R" not in ref:
            root_refs.append(ref)
    next_serial = len(root_refs) + 1
    return f"{prefix}{next_serial:03d}"


def _generate_revision_reference(existing_quotes, source_reference):
    base_reference = _get_base_reference(source_reference)
    max_revision = 0
    for quote in existing_quotes:
        ref = quote.get("Reference No", "")
        if _get_base_reference(ref) == base_reference:
            max_revision = max(max_revision, _get_revision_number(ref))
    return f"{base_reference}-R{max_revision + 1}"


def _write_quotes_excel(quotes):
    try:
        from openpyxl import Workbook
    except ImportError:
        return False, "openpyxl library is not available. Quote saved in module data, but Excel file could not be created."

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Quotes"
    sheet.append(COLUMNS)

    for quote in quotes:
        sheet.append([quote.get(column, "") for column in COLUMNS])

    for column_cells in sheet.columns:
        max_length = max(len(str(cell.value or "")) for cell in column_cells)
        sheet.column_dimensions[column_cells[0].column_letter].width = min(max(max_length + 2, 14), 45)

    workbook.save(EXCEL_FILE)
    return True, f"Excel updated at {EXCEL_FILE}"


def _save_quote_record(record, reference_no):
    quotes = _load_quotes()
    record["Reference No"] = reference_no
    record["Created At"] = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    record["Base Reference"] = _get_base_reference(reference_no)
    record["Revision No"] = _get_revision_number(reference_no)
    quotes.append(record)
    _save_quotes_json(quotes)
    excel_ok, excel_message = _write_quotes_excel(quotes)
    return excel_ok, excel_message


def _search_quotes(reference_no="", customer_name="", pol="", pod="", cargo_name=""):
    quotes = _load_quotes()
    filters = {
        "Reference No": reference_no,
        "Customer Name": customer_name,
        "POL": pol,
        "POD": pod,
        "Cargo Name": cargo_name,
    }

    filtered_quotes = []
    for quote in reversed(quotes):
        is_match = True
        for field_name, filter_value in filters.items():
            if filter_value and filter_value.lower() not in str(quote.get(field_name, "")).lower():
                is_match = False
                break
        if is_match:
            filtered_quotes.append(quote)
    return filtered_quotes


def _build_formal_rate_text(customer_name, pol, pod, cargo_name, rate_type, currency, rental_amount, free_days_from, free_days_to, thereafter_rate, local_charges, remarks):
    route_text = f"{pol} to {pod}" if pol and pod else pol or pod or ""
    cargo_label = f" (Cargo: {cargo_name})" if cargo_name else ""

    first_line = (
        f"Please be advised that the {rate_type.lower()} for the {route_text}{cargo_label} "
        f"is {currency} {rental_amount}."
    )

    second_line = ""
    if free_days_from and free_days_to and thereafter_rate:
        second_line = f" This includes {free_days_from}/{free_days_to} free days, after which a per day charge of {currency} {thereafter_rate} will apply."
    elif free_days_from and thereafter_rate:
        second_line = f" This includes {free_days_from} free days, after which a per day charge of {currency} {thereafter_rate} will apply."

    local_charges_text = f" Local charges will be {local_charges.lower()}." if local_charges else ""
    remarks_text = f"\n\nRemarks: {remarks}" if remarks else ""

    return f"{first_line}{second_line}{local_charges_text}{remarks_text}".strip()


def _build_subject_line(reference_no, pol, pod, cargo_name, customer_name):
    route_text = f"{pol} to {pod}" if pol and pod else pol or pod or ""
    cargo_text = f" [Product; {cargo_name}]" if cargo_name else ""
    customer_text = f" Customer; {customer_name}" if customer_name else ""
    return f"[{reference_no}] Oceanus Tank Rate From {route_text}{cargo_text}{customer_text}".strip()


def _build_highlighted_formal_preview(formal_text, currency, rental_amount, thereafter_rate):
    highlighted_text = formal_text.replace(
        f"{currency} {rental_amount}",
        f"<span style='color:#C62828; font-weight:700;'>{currency} {rental_amount}</span>",
        1,
    )
    if thereafter_rate:
        highlighted_text = highlighted_text.replace(
            f"{currency} {thereafter_rate}",
            f"<span style='color:#003366; font-weight:700;'>{currency} {thereafter_rate}</span>",
            1,
        )
    return highlighted_text.replace("\n\nRemarks:", "<br><br><br>Remarks:").replace("\n", "<br>")


def _render_copy_button(button_id, button_text, plain_text, html_text=None):
    escaped_plain = json.dumps(plain_text)
    clipboard_payload = f"await navigator.clipboard.writeText({escaped_plain});"
    success_text = "Copied."

    if html_text is not None:
        escaped_html = json.dumps(html_text)
        clipboard_payload = f"""
        await navigator.clipboard.write([
          new ClipboardItem({{
            'text/html': new Blob([{escaped_html}], {{ type: 'text/html' }}),
            'text/plain': new Blob([{escaped_plain}], {{ type: 'text/plain' }})
          }})
        ]);
        """
        success_text = "Copied with formatting."

    component_html = f"""
    <div>
      <button id="{button_id}" style="margin-top:8px; background:#003366; color:#FFFFFF; border:none; border-radius:8px; padding:8px 14px; cursor:pointer; font-family:Calibri, Arial, sans-serif;">
        {button_text}
      </button>
      <div id="{button_id}-msg" style="margin-top:8px; color:#0F766E; font-size:14px; font-family:Calibri, Arial, sans-serif;"></div>
    </div>
    <script>
      const btn = document.getElementById('{button_id}');
      const msg = document.getElementById('{button_id}-msg');
      btn.addEventListener('click', async () => {{
        try {{
          {clipboard_payload}
          msg.textContent = '{success_text}';
        }} catch (error) {{
          msg.textContent = 'Copy failed in this browser.';
        }}
      }});
    </script>
    """
    components.html(component_html, height=70)


def _init_form_state():
    for field_name, default_value in FORM_FIELDS.items():
        if field_name not in st.session_state:
            st.session_state[field_name] = default_value
    if "last_rate_reference" not in st.session_state:
        st.session_state.last_rate_reference = ""
    if "rate_revision_source" not in st.session_state:
        st.session_state.rate_revision_source = ""


def _load_quote_into_form(quote):
    st.session_state.customer_name = quote.get("Customer Name", "")
    st.session_state.pol = quote.get("POL", "")
    st.session_state.pod = quote.get("POD", "")
    st.session_state.cargo_name = quote.get("Cargo Name", "")
    st.session_state.rate_type = quote.get("Rate Type", "Pure Rental")
    st.session_state.currency = quote.get("Currency", "USD")
    st.session_state.rental_amount = str(quote.get("Rental Amount", ""))
    st.session_state.free_days_from = str(quote.get("Free Days From", ""))
    st.session_state.free_days_to = str(quote.get("Free Days To", ""))
    st.session_state.thereafter_rate = str(quote.get("Thereafter Rate / Day", ""))
    st.session_state.local_charges = quote.get("Local Charges", "Additional")
    st.session_state.remarks = quote.get("Remarks", "")
    st.session_state.rate_revision_source = quote.get("Reference No", "")


def _clear_revision_mode():
    st.session_state.rate_revision_source = ""


def render_rate_generation():
    st.markdown("<div class='oceanus-hero'><h1>Oceanus Line & Container Logistics LLC</h1><p>Rate Generation workspace with references, revisions, searchable history, and one-click copy actions.</p></div>", unsafe_allow_html=True)

    _init_form_state()
    create_tab, search_tab = st.tabs(["Create Quote", "Search Quotes"])

    with create_tab:
        existing_quotes = _load_quotes()
        revision_source = st.session_state.rate_revision_source
        if revision_source:
            preview_reference = _generate_revision_reference(existing_quotes, revision_source)
            st.warning(f"Revision Mode: {revision_source} -> {preview_reference}")
            if st.button("Cancel Revision", key="cancel_revision_mode"):
                _clear_revision_mode()
                st.rerun()
        else:
            preview_reference = _generate_reference_number(existing_quotes)
            st.info(f"Current Reference No: {preview_reference}")

        if st.session_state.last_rate_reference:
            st.success(f"Last Saved Reference No: {st.session_state.last_rate_reference}")

        col1, col2 = st.columns(2)

        with col1:
            customer_name = st.text_input("Customer Name", key="customer_name", placeholder="e.g., Black Rose")
            pol = st.text_input("POL (Port of Loading)", key="pol", placeholder="e.g., Hazira")
            pod = st.text_input("POD (Port of Discharge)", key="pod", placeholder="e.g., Ambarli")
            cargo_name = st.text_input("Cargo Name", key="cargo_name", placeholder="e.g., Acrylamide Solution (50%) (UN# 3426, IMDG CLASS; 6.1)")

        with col2:
            rate_type = st.selectbox("Rate Type", ["Pure Rental", "Local Leasing", "Door to Port", "Door to Door"], key="rate_type")
            currency = st.selectbox("Currency", ["USD", "INR", "AED", "SAR"], key="currency")
            rental_amount = st.text_input("Rental Amount", key="rental_amount", placeholder="e.g., 800")
            free_col1, free_col2 = st.columns(2)
            with free_col1:
                free_days_from = st.text_input("Free Days From", key="free_days_from", placeholder="e.g., 10")
            with free_col2:
                free_days_to = st.text_input("Free Days To", key="free_days_to", placeholder="e.g., 14")
            thereafter_rate = st.text_input("Thereafter Rate / Day", key="thereafter_rate", placeholder="e.g., 50")
            local_charges = st.selectbox("Local Charges", ["Additional", "Included", "At actuals", "Extra"], key="local_charges")

        remarks = st.text_area("Additional Remarks", key="remarks", placeholder="Optional notes such as subject to equipment availability, validity, etc.", height=100)

        subject_line = _build_subject_line(preview_reference, pol, pod, cargo_name, customer_name)
        formal_text = _build_formal_rate_text(
            customer_name,
            pol,
            pod,
            cargo_name,
            rate_type,
            currency,
            rental_amount,
            free_days_from,
            free_days_to,
            thereafter_rate,
            local_charges,
            remarks,
        )
        formal_preview = _build_highlighted_formal_preview(formal_text, currency, rental_amount, thereafter_rate)

        st.markdown("<div class='oceanus-section-title'>Generated Rate Text</div>", unsafe_allow_html=True)
        st.markdown("**Subject Line**")
        st.text_area("Subject Output", value=subject_line, height=80)
        _render_copy_button("copy-subject-output", "Copy Subject", subject_line)

        st.markdown("**Formal Preview**")
        st.markdown(
            f"<div style='padding:14px 16px; border:1px solid #D7E0EA; border-radius:10px; background:#FFFFFF; line-height:1.8; font-size:16px; color:#2F3B45;'>{formal_preview}</div>",
            unsafe_allow_html=True,
        )
        _render_copy_button("copy-formal-output", "Copy Formal", formal_text, formal_preview)

        save_label = "Save Revision" if revision_source else "Save Quote"
        if st.button(save_label, use_container_width=True):
            if not pol or not pod or not cargo_name or not rental_amount:
                st.error("Please fill POL, POD, Cargo Name, and Rental Amount before saving the quote.")
            else:
                record = {
                    "Subject Line": subject_line,
                    "Customer Name": customer_name,
                    "POL": pol,
                    "POD": pod,
                    "Cargo Name": cargo_name,
                    "Rate Type": rate_type,
                    "Currency": currency,
                    "Rental Amount": rental_amount,
                    "Free Days From": free_days_from,
                    "Free Days To": free_days_to,
                    "Thereafter Rate / Day": thereafter_rate,
                    "Local Charges": local_charges,
                    "Remarks": remarks,
                    "Formal Output": formal_text,
                }
                excel_ok, excel_message = _save_quote_record(record, preview_reference)
                st.session_state.last_rate_reference = preview_reference
                _clear_revision_mode()
                st.success(f"Quote saved successfully. Reference No: {preview_reference}")
                if excel_ok:
                    st.info(excel_message)
                else:
                    st.warning(excel_message)
                st.rerun()

    with search_tab:
        st.markdown("<div class='oceanus-section-title'>Search Saved Quotes</div>", unsafe_allow_html=True)
        search_col1, search_col2, search_col3 = st.columns(3)
        with search_col1:
            search_reference = st.text_input("Search by Reference No")
            search_customer = st.text_input("Search by Customer")
        with search_col2:
            search_pol = st.text_input("Search by POL")
            search_pod = st.text_input("Search by POD")
        with search_col3:
            search_cargo = st.text_input("Search by Cargo")

        filtered_quotes = _search_quotes(
            reference_no=search_reference,
            customer_name=search_customer,
            pol=search_pol,
            pod=search_pod,
            cargo_name=search_cargo,
        )

        if filtered_quotes:
            display_rows = []
            for quote in filtered_quotes:
                display_rows.append({
                    "Reference No": quote.get("Reference No", ""),
                    "Base Reference": quote.get("Base Reference", _get_base_reference(quote.get("Reference No", ""))),
                    "Revision No": quote.get("Revision No", _get_revision_number(quote.get("Reference No", ""))),
                    "Created At": quote.get("Created At", ""),
                    "Customer Name": quote.get("Customer Name", ""),
                    "POL": quote.get("POL", ""),
                    "POD": quote.get("POD", ""),
                    "Cargo Name": quote.get("Cargo Name", ""),
                    "Rate Type": quote.get("Rate Type", ""),
                    "Currency": quote.get("Currency", ""),
                    "Rental Amount": quote.get("Rental Amount", ""),
                    "Free Days From": quote.get("Free Days From", ""),
                    "Free Days To": quote.get("Free Days To", ""),
                    "Thereafter Rate / Day": quote.get("Thereafter Rate / Day", ""),
                })
            st.dataframe(display_rows, use_container_width=True, hide_index=True)

            selected_reference = st.selectbox(
                "Select Quote To Revise",
                [quote["Reference No"] for quote in filtered_quotes],
                key="selected_quote_to_revise",
            )
            if st.button("Revise This Quote", use_container_width=True):
                selected_quote = next(quote for quote in filtered_quotes if quote["Reference No"] == selected_reference)
                _load_quote_into_form(selected_quote)
                st.rerun()
        else:
            st.info("No saved quotes found for the current search filters.")



