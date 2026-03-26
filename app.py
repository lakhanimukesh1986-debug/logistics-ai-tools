import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta
import os
import json
import qrcode
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
import re
import base64
import html
from rate_generation import render_rate_generation
from cleaning_module import render_cleaning_module

# ---------- COLORS ----------
OCEANUS_BLUE = (0, 51, 102)
LIGHT_BLUE = (240, 248, 255)
ACCENT_RED = (200, 0, 0)

# ---------- STORAGE ----------
if not os.path.exists("DO_History"):
    os.makedirs("DO_History")
if not os.path.exists("email_config"):
    os.makedirs("email_config")

DEPOT_FILE = "depots.json"
EMAIL_CONFIG_FILE = "email_config/email_config.json"
DEPOT_EMAIL_FILE = "email_config/depot_emails.json"

# ========== HELPER FUNCTIONS ==========
def shorten_depot_name(full_name):
    name = re.sub(r'(?i)^m/s\.?\s*', '', full_name)
    ignore_words = {
        'marine', 'service', 'services', 'logistics', 'terminal',
        'container', 'pvt', 'ltd', 'private', 'limited', 'yard',
        'depot', 'pvt.', 'ltd.', 'co.', 'company', 'corp'
    }
    words = name.split()
    filtered_words = [w for w in words if re.sub(r'[.,]', '', w).lower() not in ignore_words]
    short_name = re.sub(r'[,.-]+$', '', " ".join(filtered_words)).strip()
    if not short_name:
        short_name = full_name.split()[0] if full_name.split() else ""
    return f"{short_name} Depot" if short_name else "Depot"

# ========== EMAIL CONFIGURATION ==========
def load_email_config():
    if os.path.exists(EMAIL_CONFIG_FILE):
        with open(EMAIL_CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"sender_email": "", "sender_password": "", "smtp_server": "smtp.gmail.com", "smtp_port": 587}

def save_email_config(config):
    with open(EMAIL_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def load_depot_emails():
    if os.path.exists(DEPOT_EMAIL_FILE):
        with open(DEPOT_EMAIL_FILE, "r") as f:
            return json.load(f)
    return {}

def save_depot_emails(data):
    with open(DEPOT_EMAIL_FILE, "w") as f:
        json.dump(data, f, indent=4)

def validate_email(email):
    return re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email) is not None


def parse_email_lines(raw_text):
    return [line.strip() for line in raw_text.splitlines() if line.strip()]


def find_invalid_emails(emails):
    return [email for email in emails if not validate_email(email)]

def create_professional_email_html(customer_name, tank_count, tanks, do_num, dynamic_instructions):
    issue_date = datetime.now().strftime('%d-%m-%Y')
    valid_date = (datetime.now() + timedelta(days=7)).strftime('%d-%m-%Y')
    formatted_instructions = dynamic_instructions.replace('\n', '<br>')

    # Tank rows â€” zebra striped, monospace Calibri font, no ISO Tank label
    tank_rows = ""
    for i, tank in enumerate(tanks):
        bg = "#F8FAFC" if i % 2 == 0 else "#FFFFFF"
        tank_rows += f"""
        <tr style="background-color:{bg};">
            <td style="padding:8px 12px; color:#AAAAAA; font-size:11px; 
                font-family:Calibri,Arial,sans-serif; width:32px; border:1px solid #EEEEEE;">
                <b>0{i+1}</b>
            </td>
            <td style="padding:8px 16px; color:#003366; font-size:11px; font-weight:bold;
                font-family:Calibri,Arial,sans-serif; letter-spacing:0.5px; border:1px solid #EEEEEE;">
                {tank}
            </td>
        </tr>"""

    sig_html = '<img src="cid:signature" alt="Signature" style="max-width:250px; height:auto; margin-top:8px;">' if os.path.exists("signature.png") else ''

    html_body = f"""
<html>
<head><meta charset='UTF-8'></head>
<body style="font-family:Calibri,Arial,sans-serif; font-size:11px; color:#2C2C2C;
     line-height:1.6; margin:0; padding:20px 24px; background:#ffffff;">

  <div style="max-width:780px;">

    <p style="margin:0 0 6px 0; font-size:11px;">Dear Team,</p>

    <p style="font-size:11px; color:#444; margin:0 0 10px 0; text-align:justify;">
      We hope this message finds you well. Kindly be advised that our valued customer,
      <strong style="color:#003366;">{customer_name}</strong>, has scheduled a pick-up of
      <strong style="color:#003366;">{tank_count} tank(s)</strong> today from your facility.
    </p>

    <p style="font-size:11px; color:#444; margin:0 0 14px 0; text-align:justify;">
      We kindly request your team to carry out a thorough inspection of the unit(s) â€” both
      <strong>internally and externally</strong> â€” prior to handover. Please ensure the tanks are
      completely free from dust, oil marks, odour, moisture, and any issues with fittings or
      seaworthiness. Kindly coordinate with the customer's nominated transporter accordingly.
    </p>

    <!-- TANK NUMBERS â€” Zebra Striped Clean Table -->
    <div style="margin:0 0 14px 0;">
      <p style="margin:0 0 6px 0; color:#7F8C8D; font-size:10px; font-weight:bold;
         letter-spacing:1px; text-transform:uppercase; font-family:Calibri,Arial,sans-serif;">
        Tank Number(s)
      </p>
      <table style="border-collapse:collapse; width:auto; min-width:280px;">
        {tank_rows}
      </table>
    </div>

    <!-- DELIVERY ORDER DETAILS â€” Blue top border, clean rows -->
    <div style="margin:0 0 14px 0;">
      <div style="border-top:2px solid #003366; padding-top:8px; margin-bottom:4px;">
        <span style="color:#003366; font-size:10px; font-weight:bold; font-family:Calibri,Arial,sans-serif;
              text-transform:uppercase; letter-spacing:0.8px;">Delivery Order Details</span>
      </div>
      <table style="border-collapse:collapse; width:100%; max-width:420px;">
        <tr style="border-bottom:1px solid #F0F0F0;">
          <td style="padding:5px 0; color:#888; font-size:11px; font-family:Calibri,Arial,sans-serif; width:130px;">DO Number</td>
          <td style="padding:5px 0; color:#003366; font-size:11px; font-weight:bold; font-family:Calibri,Arial,sans-serif;">{do_num}</td>
        </tr>
        <tr style="border-bottom:1px solid #F0F0F0;">
          <td style="padding:5px 0; color:#888; font-size:11px; font-family:Calibri,Arial,sans-serif;">Date of Issue</td>
          <td style="padding:5px 0; color:#333; font-size:11px; font-weight:600; font-family:Calibri,Arial,sans-serif;">{issue_date}</td>
        </tr>
        <tr>
          <td style="padding:5px 0; color:#888; font-size:11px; font-family:Calibri,Arial,sans-serif;">Valid Until</td>
          <td style="padding:5px 0; color:#C62828; font-size:11px; font-weight:bold; font-family:Calibri,Arial,sans-serif;">{valid_date}</td>
        </tr>
      </table>
    </div>

    <!-- SPECIAL INSTRUCTIONS â€” Blue top border, dynamic -->
    <div style="margin:0 0 16px 0;">
      <div style="border-top:2px solid #003366; padding-top:8px; margin-bottom:6px;">
        <span style="color:#003366; font-size:10px; font-weight:bold; font-family:Calibri,Arial,sans-serif;
              text-transform:uppercase; letter-spacing:0.8px;">Special Instructions &amp; Requirements</span>
      </div>
      <p style="margin:0; color:#555; font-size:11px; line-height:1.75; font-family:Calibri,Arial,sans-serif;">
        {formatted_instructions}
      </p>
    </div>

    <!-- CLOSING -->
    <p style="font-size:11px; color:#555; margin:0 0 4px 0; font-family:Calibri,Arial,sans-serif;">
      Your prompt attention to this matter is greatly appreciated. Please do not hesitate to reach out should you require any further information.
    </p>
    <p style="font-size:11px; color:#555; margin:0 0 14px 0; font-family:Calibri,Arial,sans-serif;">
      Thank you for your continued cooperation.
    </p>

    <!-- SIGNATURE -->
    <div style="margin-top:6px;">{sig_html}</div>

  </div>
</body>
</html>
"""
    return html_body

def create_professional_email_html_v2(customer_name, tank_count, tanks, do_num, dynamic_instructions):
    issue_date = datetime.now().strftime('%d-%m-%Y')
    valid_date = (datetime.now() + timedelta(days=7)).strftime('%d-%m-%Y')
    safe_customer_name = html.escape(customer_name)
    safe_do_num = html.escape(do_num)
    tank_label = "1 tank" if tank_count == 1 else f"{tank_count} tank(s)"

    instruction_lines = [line.strip() for line in dynamic_instructions.splitlines() if line.strip()]
    formatted_instructions = "".join(
        f'<li style="margin:0 0 6px 0;">{html.escape(re.sub(r"^\d+\.\s*", "", line))}</li>'
        for line in instruction_lines
    )
    if not formatted_instructions:
        formatted_instructions = '<li style="margin:0;">Please follow the standard Oceanus Line release order handling instructions.</li>'

    left_tanks = tanks[:10]
    right_tanks = tanks[10:20]
    left_rows = ""
    for i, tank in enumerate(left_tanks):
        left_rows += f"""
        <tr>
          <td style="border:1px solid #1F4E79; padding:10px 8px; text-align:center; width:70px;">{i + 1}</td>
          <td style="border:1px solid #1F4E79; padding:10px 14px; text-align:center; min-width:260px; font-weight:700; color:#003366;">{html.escape(tank)}</td>
        </tr>"""

    right_rows = ""
    for i, tank in enumerate(right_tanks):
        right_rows += f"""
        <tr>
          <td style="border:1px solid #1F4E79; padding:10px 8px; text-align:center; width:70px;">{i + 11}</td>
          <td style="border:1px solid #1F4E79; padding:10px 14px; text-align:center; min-width:260px; font-weight:700; color:#003366;">{html.escape(tank)}</td>
        </tr>"""

    right_table_html = ""
    if right_rows:
        right_table_html = f"""
      <table style="border-collapse:collapse; font-size:15px;">
        <tr style="background:#EAF2FB; font-weight:700;">
          <td style="border:1px solid #1F4E79; padding:10px 8px; text-align:center; width:70px;">S.No</td>
          <td style="border:1px solid #1F4E79; padding:10px 14px; text-align:center; min-width:260px;">Tank Number</td>
        </tr>
        {right_rows}
      </table>"""

    sig_html = ""
    if os.path.exists("signature.png"):
        sig_html = '<img src="cid:signature" alt="Signature" style="max-width:280px; width:100%; height:auto; margin-top:6px; display:block;">'

    return f"""
<html>
<head><meta charset='UTF-8'></head>
<body style="font-family:Calibri,Arial,sans-serif; font-size:15px; color:#333333; line-height:1.7; margin:0; padding:24px; background:#FFFFFF;">
  <div style="max-width:760px; margin:0 auto;">
    <div style="margin:0 0 18px 0; font-size:18px; line-height:1.75; color:#2F3B45;">
      <p style="margin:0 0 14px 0; font-size:18px; color:#2F3B45;">Dear Team,</p>

      <p style="margin:0 0 14px 0; font-size:18px; color:#2F3B45;">
        We hope this message finds you well. Kindly be advised that our valued customer,
        <strong style="color:#003366;">{safe_customer_name}</strong>, has scheduled a pick-up of
        <strong style="color:#C62828;">{tank_label}</strong> today from your facility.
      </p>

      <p style="margin:0; font-size:18px; color:#2F3B45;">
        We kindly request your team to carry out a thorough inspection of the unit(s), both internally and externally,
        prior to handover. Please ensure the tanks are completely free from dust, oil marks, odour, moisture,
        and any issues with fittings or seaworthiness. Kindly coordinate with the customer's nominated transporter accordingly.
      </p>
    </div>

    <p style="margin:0 0 8px 0; font-weight:700; font-size:15px; color:#003366; text-transform:uppercase; letter-spacing:0.6px;">Tank Number(s)</p>
    <div style="margin:0 0 30px 0;">
      <table style="border-collapse:collapse;">
        <tr>
          <td style="vertical-align:top; padding:0 18px 0 0;">
            <table style="border-collapse:collapse; font-size:15px;">
              <tr style="background:#EAF2FB; font-weight:700;">
                <td style="border:1px solid #1F4E79; padding:10px 8px; text-align:center; width:70px;">S.No</td>
                <td style="border:1px solid #1F4E79; padding:10px 14px; text-align:center; min-width:260px;">Tank Number</td>
              </tr>
              {left_rows}
            </table>
          </td>
          <td style="vertical-align:top;">
            {right_table_html}
          </td>
        </tr>
      </table>
    </div>

    <p style="margin:0 0 8px 0; font-weight:700; font-size:15px; color:#003366; text-transform:uppercase; letter-spacing:0.6px;">Special Instructions &amp; Requirements</p>
    <ol style="margin:0 0 16px 22px; padding:0; font-size:15px;">
      {formatted_instructions}
    </ol>

    <div style="margin-top:8px;">
      {sig_html}
    </div>
  </div>
</body>
</html>
"""

def send_email_with_attachment(recipient_emails, cc_emails, subject, html_body, pdf_file_path, sender_email, sender_password):
    try:
        if not os.path.exists(pdf_file_path):
            return False, f"Attachment Error: Could not find PDF file at {pdf_file_path}"

        if isinstance(recipient_emails, str):
            recipient_emails = [recipient_emails]

        msg = MIMEMultipart('mixed')
        msg['From'] = sender_email
        msg['To'] = ', '.join(recipient_emails)
        if cc_emails:
            msg['Cc'] = ', '.join(cc_emails)
        msg['Subject'] = subject

        msg_related = MIMEMultipart('related')
        msg.attach(msg_related)
        msg_alternative = MIMEMultipart('alternative')
        msg_related.attach(msg_alternative)
        msg_alternative.attach(MIMEText(html_body, 'html'))

        if os.path.exists("signature.png"):
            with open("signature.png", "rb") as f:
                sig_img = MIMEImage(f.read())
                sig_img.add_header('Content-ID', '<signature>')
                sig_img.add_header('Content-Disposition', 'inline', filename='signature.png')
                msg_related.attach(sig_img)

        with open(pdf_file_path, "rb") as f:
            attach_part = MIMEApplication(f.read(), _subtype="pdf")
        attach_part.add_header('Content-Disposition', 'attachment', filename=os.path.basename(pdf_file_path))
        msg.attach(attach_part)

        all_recipients = recipient_emails + (cc_emails if cc_emails else [])
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, all_recipients, msg.as_string())
        server.quit()
        return True, "Email sent successfully with Signature & PDF!"
    except smtplib.SMTPAuthenticationError:
        return False, "Invalid email or password! Check Gmail credentials."
    except smtplib.SMTPException as e:
        return False, f"SMTP Error: {str(e)}"
    except Exception as e:
        return False, f"Error: {str(e)}"

# ========== DEPOT MANAGEMENT ==========
def load_depots():
    if os.path.exists(DEPOT_FILE):
        with open(DEPOT_FILE, "r") as f:
            data = json.load(f)
            return {k: v if isinstance(v, dict) else {'address': v, 'url': ''} for k, v in data.items()}
    return {}

def save_depots(data):
    with open(DEPOT_FILE, "w") as f:
        json.dump(data, f, indent=4)

DEPOTS = load_depots()

STD_REQS = """1. This D/O is valid for 07 days from date of issue for picking up containers from yard.
2. Empty tank to be ventilated a day prior to ensure that it is odour free.
3. Ensure that the tank is completely clean and odour free.
4. Need RFID Seal provision.
5. Pressure gauge in working condition.
6. Please send internal and external tank photos after preparation of tank."""

# ========== PAGE CONFIG ==========
st.set_page_config(page_title="Oceanus Line & Container Logistics LLC", layout="wide")

st.markdown("""
<style>
    .stApp {
        background: radial-gradient(circle at top, #17324d 0%, #0b1623 58%, #07111b 100%);
    }
    .block-container {
        padding-top: 1.4rem;
        padding-bottom: 2rem;
        max-width: 1320px;
    }
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #081320 0%, #0d2136 100%);
        border-right: 1px solid rgba(255,255,255,0.08);
    }
    section[data-testid="stSidebar"] * {
        color: #f5f7fb;
    }
    .main .block-container,
    .main .block-container label,
    .main .block-container p,
    .main .block-container h1,
    .main .block-container h2,
    .main .block-container h3,
    .main .block-container h4,
    .main .block-container h5,
    .main .block-container h6,
    .main .block-container span,
    .main .block-container div,
    .main .block-container [data-testid="stWidgetLabel"],
    .main .block-container [data-testid="stWidgetLabel"] * {
        color: #eef4fb !important;
    }
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div,
    div[data-baseweb="textarea"] > div {
        border-radius: 14px !important;
        border: 1px solid #2a4664 !important;
        background: rgba(10, 24, 38, 0.92) !important;
        box-shadow: 0 10px 24px rgba(0, 0, 0, 0.22);
    }
    .main .block-container input,
    .main .block-container textarea,
    .main .block-container [data-baseweb="select"] input,
    .main .block-container [data-baseweb="select"] span,
    .main .block-container [data-baseweb="select"] div {
        color: #f4f8fc !important;
        -webkit-text-fill-color: #f4f8fc !important;
    }
    .main .block-container input::placeholder,
    .main .block-container textarea::placeholder {
        color: #9ab0c6 !important;
        -webkit-text-fill-color: #9ab0c6 !important;
        opacity: 1 !important;
    }
    .stButton > button {
        border-radius: 14px !important;
        border: 1px solid #1c5a8d !important;
        background: linear-gradient(135deg, #114a79 0%, #1a6a96 100%) !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        min-height: 2.8rem;
        box-shadow: 0 10px 24px rgba(10, 44, 77, 0.28);
    }
    .stDownloadButton > button {
        border-radius: 14px !important;
    }
    div[data-testid="stExpander"] {
        background: rgba(9, 22, 35, 0.72);
        border: 1px solid #233c56;
        border-radius: 18px;
        box-shadow: 0 10px 26px rgba(0, 0, 0, 0.18);
    }
    div[data-testid="stExpander"] summary,
    div[data-testid="stExpander"] summary * {
        color: #eef4fb !important;
    }
    div[data-testid="stTabs"] button {
        border-radius: 12px 12px 0 0 !important;
        font-weight: 600 !important;
        color: #a9bfd3 !important;
    }
    div[data-testid="stTabs"] button[aria-selected="true"] {
        color: #ffffff !important;
    }
    div[data-testid="stDataFrame"] {
        background: rgba(8, 20, 32, 0.85);
        border: 1px solid #233c56;
        border-radius: 18px;
        overflow: hidden;
        box-shadow: 0 10px 26px rgba(0, 0, 0, 0.18);
    }
    div[data-testid="stAlert"] {
        border-radius: 16px;
    }
    .oceanus-hero {
        background: linear-gradient(135deg, #0f3d66 0%, #174d7c 55%, #1a6e8c 100%);
        color: #ffffff !important;
        border-radius: 24px;
        padding: 26px 30px;
        margin-bottom: 18px;
        box-shadow: 0 18px 38px rgba(15, 61, 102, 0.24);
    }
    .oceanus-hero h1,
    .oceanus-hero p {
        color: #ffffff !important;
    }
    .oceanus-hero h1 {
        margin: 0;
        font-size: 2.2rem;
        font-weight: 800;
        letter-spacing: -0.02em;
    }
    .oceanus-hero p {
        margin: 8px 0 0 0;
        font-size: 1rem;
        opacity: 0.92;
    }
    .oceanus-section-title {
        color: #eef4fb !important;
        font-weight: 700;
        letter-spacing: 0.02em;
    }
</style>
""", unsafe_allow_html=True)

# ========== SIDEBAR ==========
with st.sidebar:
    page_mode = st.radio("Module", ["DO Generation", "Rate Generation", "Cleaning Module"] )
    st.markdown("---")
    st.markdown("## System Settings")

    with st.expander("Email Configuration", expanded=False):
        st.markdown("**Gmail SMTP Setup:**")
        st.info("""
        Get Gmail App Password:
        1. Go: myaccount.google.com
        2. Click: Security
        3. Search: "App passwords"
        4. Select: Mail -> Windows
        5. Copy 16-character password
        """)
        email_config = load_email_config()
        new_sender_email = st.text_input("Gmail Address", value=email_config.get('sender_email', ''), placeholder="your.email@gmail.com")
        new_sender_password = st.text_input("App Password (16 characters)", value=email_config.get('sender_password', ''), type="password", placeholder="xxxx xxxx xxxx xxxx")
        if st.button("Save Configuration", use_container_width=True):
            if new_sender_email and new_sender_password:
                email_config['sender_email'] = new_sender_email
                email_config['sender_password'] = new_sender_password
                save_email_config(email_config)
                st.success("Email configuration saved!")
            else:
                st.error("Please fill both fields!")

    with st.expander("Manage Depot Emails", expanded=False):
        st.markdown("**Add/Edit/Delete Depot Contact Emails**")
        depot_emails = load_depot_emails()
        DEPOTS = load_depots()
        tab1, tab2, tab3 = st.tabs(["Add", "Edit", "Delete"])

        with tab1:
            depot_select = st.selectbox("Select Depot", list(DEPOTS.keys()), key="add_depot_email")
            depot_to_email = st.text_area("To Email Addresses (one per line)", placeholder="depot@example.com", height=100)
            depot_cc_emails = st.text_area("CC Emails (one per line, optional)", height=100)
            if st.button("Add Depot Email", use_container_width=True):
                if depot_select and depot_to_email:
                    to_list = parse_email_lines(depot_to_email)
                    cc_list = parse_email_lines(depot_cc_emails)
                    invalid_emails = find_invalid_emails(to_list + cc_list)
                    if to_list and not invalid_emails:
                        depot_emails[depot_select] = {'to_email': to_list, 'cc_emails': cc_list}
                        save_depot_emails(depot_emails)
                        st.success(f"Email added for {depot_select}!")
                        st.rerun()
                    else:
                        st.error(f"Invalid email format: {', '.join(invalid_emails)}" if invalid_emails else "Please enter at least one To email.")

        with tab2:
            if depot_emails:
                edit_depot = st.selectbox("Select Depot to Edit", list(depot_emails.keys()), key="edit_depot_email")
                curr_data = depot_emails[edit_depot]
                existing_to = curr_data.get('to_email', [])
                if isinstance(existing_to, str):
                    existing_to = [existing_to]
                edit_to_email = st.text_area("To Emails (one per line)", value='\n'.join(existing_to), height=100)
                edit_cc_emails = st.text_area("CC Emails (one per line)", value=''.join([x + '\n' for x in curr_data.get('cc_emails', [])]).rstrip(), height=100)
                if st.button("Update Email", use_container_width=True):
                    to_list = parse_email_lines(edit_to_email)
                    cc_list = parse_email_lines(edit_cc_emails)
                    invalid_emails = find_invalid_emails(to_list + cc_list)
                    if to_list and not invalid_emails:
                        depot_emails[edit_depot] = {'to_email': to_list, 'cc_emails': cc_list}
                        save_depot_emails(depot_emails)
                        st.success("Updated!")
                        st.rerun()
                    else:
                        st.error(f"Invalid email format: {', '.join(invalid_emails)}" if invalid_emails else "Please enter at least one To email.")
            else:
                st.info("No depot emails configured yet.")

        with tab3:
            if depot_emails:
                del_depot = st.selectbox("Select Depot to Delete", list(depot_emails.keys()), key="del_depot_email")
                if st.button("Delete Email", use_container_width=True):
                    del depot_emails[del_depot]
                    save_depot_emails(depot_emails)
                    st.success(f"Email deleted for {del_depot}!")
                    st.rerun()
            else:
                st.info("No depot emails to delete!")

if page_mode == "Rate Generation":
    render_rate_generation()
    st.stop()

if page_mode == "Cleaning Module":
    render_cleaning_module()
    st.stop()

# ========== MAIN PAGE ==========
st.markdown("<div class='oceanus-hero'><h1>Oceanus Line & Container Logistics LLC</h1><p>Professional depot notification workflow for release orders, PDF generation, and email dispatch.</p></div>", unsafe_allow_html=True)


with st.expander("Manage Depots"):
    tab1, tab2, tab3 = st.tabs(["Add", "Edit", "Delete"])

    with tab1:
        new_name = st.text_input("Depot Name", placeholder="e.g., M/s OSM Marine Service")
        new_address = st.text_area("Depot Address", height=100)
        new_map_url = st.text_input("Google Maps Link (Optional)", placeholder="https://maps.google.com/...")
        if st.button("Add Depot", use_container_width=True):
            if new_name and new_address:
                DEPOTS[new_name] = {'address': new_address, 'url': new_map_url}
                save_depots(DEPOTS)
                st.success("Depot added!")
                st.rerun()

    with tab2:
        if DEPOTS:
            edit_name = st.selectbox("Select Depot to Edit", list(DEPOTS.keys()))
            curr_data = DEPOTS[edit_name]
            curr_addr = curr_data['address'] if isinstance(curr_data, dict) else curr_data
            curr_url = curr_data.get('url', '') if isinstance(curr_data, dict) else ''
            edit_address = st.text_area("Address", value=curr_addr, height=100)
            edit_url = st.text_input("Map Link", value=curr_url)
            if st.button("Update Depot", use_container_width=True):
                DEPOTS[edit_name] = {'address': edit_address, 'url': edit_url}
                save_depots(DEPOTS)
                st.success("Updated!")
                st.rerun()

    with tab3:
        if DEPOTS:
            del_name = st.selectbox("Select Depot to Delete", list(DEPOTS.keys()))
            if st.button("Delete Depot", use_container_width=True):
                del DEPOTS[del_name]
                save_depots(DEPOTS)
                st.success("Deleted!")
                st.rerun()

st.markdown("---")
DEPOTS = load_depots()
if not DEPOTS:
    st.warning("Please add at least one depot first!")
    st.stop()

# -------- MAIN FORM --------
st.markdown("### Release Order Details")
col1, col2 = st.columns(2)

with col1:
    depot_name = st.selectbox("Select Depot", list(DEPOTS.keys()))
    customer = st.text_input("Customer Name", placeholder="e.g., ABC Shipping Ltd")
    operation_type = st.selectbox("Operation Type", ["Export", "Empty Reposition"])

with col2:
    st.markdown("**Tank Information**")
    tank_input = st.text_area("Tank Numbers (one per line)", height=150, placeholder="TANK001\nTANK002\nTANK003")

reqs = st.text_area("Special Instructions", value=STD_REQS, height=170)

class PDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

st.markdown("---")
st.markdown("### Actions")
col_gen, col_notify = st.columns(2)

with col_gen:
    if st.button("Generate Release Order", use_container_width=True):
        if not customer or not tank_input:
            st.error("Please fill in Customer Name and Tank Numbers!")
        else:
            tanks = [t.strip() for t in tank_input.split('\n') if t.strip()]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            type_code = "EXP" if operation_type == "Export" else "EMP"
            do_num = f"OL/{type_code}/{depot_name[:3].upper()}/{datetime.now().strftime('%y%m%d%H%M')}"
            valid_date = (datetime.now() + timedelta(days=7)).strftime('%d-%m-%Y')

            pdf = PDF(unit='mm', format='A4')
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)

            if os.path.exists("logo.png"):
                pdf.image('logo.png', 12, 10, 45)

            pdf.set_font("Helvetica", 'B', 14)
            pdf.set_text_color(*OCEANUS_BLUE)
            pdf.set_xy(100, 12)
            pdf.cell(98, 7, "OCEANUS LINE AND CONTAINER LOGISTICS LLC", 0, 1, 'R')
            pdf.set_font("Helvetica", '', 7.5)
            pdf.set_x(100)
            pdf.multi_cell(98, 3.5, "OFFICE NO 502, AL WASL BUILDING OPP CIVIL DEFENCE,\nAL KARAMA, DUBAI, UAE, PO BOX 62565", 0, 'R')

            pdf.ln(5)
            pdf.set_draw_color(*OCEANUS_BLUE)
            pdf.set_line_width(1.0)
            pdf.line(12, 38, 198, 38)

            pdf.set_y(42)
            pdf.set_fill_color(*LIGHT_BLUE)
            pdf.rect(12, 42, 186, 10, 'F')
            pdf.set_font("Helvetica", 'B', 14)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 10, "DELIVERY ORDER / RELEASE ORDER", 0, 1, 'C')
            pdf.ln(5)

            pdf.set_fill_color(245, 247, 250)
            pdf.set_draw_color(*OCEANUS_BLUE)
            pdf.set_line_width(0.3)

            pdf.set_font("Helvetica", 'B', 9)
            pdf.cell(35, 8, " DO NUMBER:", 1, 0, 'L', True)
            pdf.set_font("Helvetica", '', 10)
            pdf.cell(85, 8, f" {do_num}", 1, 0)
            pdf.set_font("Helvetica", 'B', 9)
            pdf.cell(30, 8, " DATE:", 1, 0, 'L', True)
            pdf.set_font("Helvetica", '', 10)
            pdf.cell(40, 8, f" {datetime.now().strftime('%d-%m-%Y')}", 1, 1)

            pdf.set_font("Helvetica", 'B', 9)
            pdf.cell(35, 10, " CUSTOMER:", 1, 0, 'L', True)
            pdf.set_font("Helvetica", 'B', 11)
            pdf.cell(85, 10, f" {customer.upper()}", 1, 0)
            pdf.set_font("Helvetica", 'B', 9)
            pdf.cell(30, 10, " VALID UNTIL:", 1, 0, 'L', True)
            pdf.set_text_color(*ACCENT_RED)
            pdf.set_font("Helvetica", 'B', 10)
            pdf.cell(40, 10, f" {valid_date}", 1, 1)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(4)

            depot_data = DEPOTS[depot_name]
            addr_text = depot_data['address'] if isinstance(depot_data, dict) else depot_data
            map_url = depot_data.get('url', '') if isinstance(depot_data, dict) else ''

            pdf.set_font("Helvetica", 'B', 9)
            pdf.cell(35, 8, " DEPOT NAME:", 1, 0, 'L', True)
            pdf.set_font("Helvetica", '', 10)
            pdf.cell(155, 8, f" {depot_name}", 1, 1)

            address_lines = addr_text.split('\n')
            line_height = 5
            text_height = max(len(address_lines) * line_height, 10) + 4
            min_qr_height = 28
            final_height = max(text_height, min_qr_height) if map_url else text_height

            y_start = pdf.get_y()
            x_start = pdf.get_x()

            pdf.set_font("Helvetica", 'B', 9)
            pdf.cell(35, final_height, " ADDRESS:", "L", 0, 'L', True)

            w_addr = 120 if map_url else 155
            x_text = pdf.get_x()
            current_text_y = pdf.get_y() + 2

            for line in address_lines:
                pdf.set_xy(x_text, current_text_y)
                pdf.set_font("Helvetica", 'B' if ("+" in line or any(c.isdigit() for c in line)) else '', 10 if ("+" in line or any(c.isdigit() for c in line)) else 9)
                pdf.cell(w_addr, line_height, line, 0, 0)
                current_text_y += line_height

            if map_url:
                qr = qrcode.QRCode(box_size=10, border=1)
                qr.add_data(map_url)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                temp_qr_path = "temp_qr.png"
                img.save(temp_qr_path)
                qr_size = 22
                pdf.image(temp_qr_path, x=(x_start + 35 + w_addr) + (35 - qr_size) / 2, y=y_start + (final_height - qr_size) / 2, w=qr_size)
                pdf.line(x_start + 35 + w_addr, y_start, x_start + 35 + w_addr, y_start + final_height)

            pdf.set_draw_color(*OCEANUS_BLUE)
            pdf.rect(x_start, y_start, 190, final_height)
            pdf.line(x_start + 35, y_start, x_start + 35, y_start + final_height)
            pdf.set_y(y_start + final_height + 8)

            pdf.set_font("Helvetica", '', 11)
            pdf.write(6, "We have allotted the following Mty Unit/s to the ")
            pdf.write(6, "Shipper Messrs. " if operation_type == "Export" else "Transporter Messrs. ")
            pdf.set_font("Helvetica", 'B', 11)
            pdf.write(6, customer.upper())
            pdf.set_font("Helvetica", '', 11)
            pdf.write(6, " for Factory Stuffing." if operation_type == "Export" else " for empty reposition.")
            pdf.ln(10)

            total_tanks = len(tanks)
            cols = 1 if total_tanks <= 10 else (2 if total_tanks <= 20 else 3)
            w_sno, w_tank, h_cell = 10, 52, 7
            rows_count = total_tanks if total_tanks <= 10 else 10

            pdf.set_draw_color(*OCEANUS_BLUE)
            pdf.set_fill_color(*LIGHT_BLUE)
            pdf.set_font("Helvetica", 'B', 9)
            pdf.set_text_color(0, 0, 0)

            for _ in range(cols):
                pdf.cell(w_sno, h_cell, "S.No", 1, 0, 'C', True)
                pdf.cell(w_tank, h_cell, "Tank Number", 1, 0, 'C', True)
            pdf.ln()

            pdf.set_font("Helvetica", '', 9)
            for r in range(rows_count):
                for col_idx, offset in enumerate([0, 10, 20]):
                    if col_idx < cols:
                        idx = r + offset
                        pdf.cell(w_sno, h_cell, str(idx + 1) if idx < total_tanks else "", 1, 0, 'C')
                        pdf.cell(w_tank, h_cell, tanks[idx] if idx < total_tanks else "", 1, 0, 'C')
                pdf.ln()

            pdf.ln(8)
            if pdf.get_y() > 220:
                pdf.add_page()

            pdf.set_font("Helvetica", 'B', 12)
            pdf.set_text_color(*OCEANUS_BLUE)
            pdf.cell(0, 8, "Special Instructions / Requirements:", 0, 1)
            pdf.set_draw_color(200, 200, 200)
            pdf.line(12, pdf.get_y(), 100, pdf.get_y())
            pdf.ln(2)
            pdf.set_font("Helvetica", '', 9)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(0, 5, reqs)

            pdf.set_y(-20)
            pdf.set_font("Helvetica", 'B', 7)
            pdf.cell(0, 5, "THIS IS A COMPUTER GENERATED DOCUMENT AND DOES NOT REQUIRE A PHYSICAL SIGNATURE.", 0, 0, 'C')

            file_path = f"DO_History/DO_{customer.replace(' ', '_')}_{timestamp}.pdf"
            pdf.output(file_path)

            st.session_state.generated_pdf_path = file_path
            st.session_state.generated_do_num = do_num
            st.session_state.generated_customer = customer
            st.session_state.generated_depot = depot_name
            st.session_state.generated_tanks = tanks
            st.session_state.generated_reqs = reqs
            st.session_state.generated_op_type = operation_type
            st.success("Release Order Generated Successfully!")
            with open(file_path, "rb") as f:
                st.download_button("Download PDF", f, file_name=f"DO_{customer}_{timestamp}.pdf", use_container_width=True)

# ========== DEPOT NOTIFICATION ==========
with col_notify:
    if st.button("Notify Depot", use_container_width=True):
        if 'generated_pdf_path' not in st.session_state:
            st.error("Generate Release Order first!")
        else:
            depot_emails = load_depot_emails()
            if depot_name not in depot_emails:
                st.error(f"No email configured for {depot_name}!")
                st.info("Go to Sidebar -> Manage Depot Emails -> Add Email")
            else:
                email_config = load_email_config()
                if not email_config.get('sender_email') or not email_config.get('sender_password'):
                    st.error("Gmail not configured!")
                    st.info("Go to Sidebar -> Email Configuration -> Save")
                else:
                    with st.spinner("Sending professional email..."):
                        depot_info = depot_emails[depot_name]
                        to_email = depot_info['to_email']
                        if isinstance(to_email, str):
                            to_email = [to_email]
                        cc_emails = depot_info.get('cc_emails', [])
                        tanks = st.session_state.generated_tanks
                        tank_count = len(tanks)
                        tank_subject_label = "1 ISO Tank" if tank_count == 1 else f"{tank_count:02d} ISO Tanks"
                        short_depot_name = shorten_depot_name(st.session_state.generated_depot)
                        tank_str = ", ".join(tanks) if 1 < tank_count <= 4 else tank_subject_label
                        op_type_str = "Export" if st.session_state.generated_op_type == "Export" else "Empty Reposition"
                        subject = f"{short_depot_name} / Oceanus Line : Pick-up Of Tank# {tank_str} // For {op_type_str} Shipment [Customer; {st.session_state.generated_customer}]"

                        html_body = create_professional_email_html_v2(
                            st.session_state.generated_customer,
                            tank_count,
                            tanks,
                            st.session_state.generated_do_num,
                            st.session_state.generated_reqs
                        )

                        success, message = send_email_with_attachment(
                            to_email, cc_emails, subject, html_body,
                            st.session_state.generated_pdf_path,
                            email_config['sender_email'],
                            email_config['sender_password']
                        )

                        if success:
                            st.success(f"Email sent successfully to: {', '.join(to_email)} with PDF & Signature!")
                            if cc_emails:
                                st.info(f"CC: {', '.join(cc_emails)}")
                            st.balloons()
                        else:
                            st.error(message)









