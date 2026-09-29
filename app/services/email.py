"""Gmail API sending and all system email templates."""

from google.oauth2.credentials import Credentials
from decimal import Decimal
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo
import asyncio
import base64
from googleapiclient.discovery import build
import datetime
from sqlalchemy.orm import object_session
import os
import re

from app.config import (
    WEB_DIR,
    CONTACT_RECEIVER_EMAIL,
    GMAIL_CLIENT_ID,
    GMAIL_CLIENT_SECRET,
    GMAIL_FROM_NAME,
    GMAIL_REFRESH_TOKEN,
    GMAIL_SCOPES,
    GMAIL_SENDER_EMAIL,
)
from app.models import (
    StoreItem,
)
from app.schemas import (
    ContactRequest,
)
from app.services.qr import (
    generate_participant_qr,
)

# ======================================================
# VALIDATE GMAIL CONFIGURATION
# ======================================================

def _validate_gmail_config():
    """
    Make sure all required Gmail environment variables
    are configured.

    This does NOT expose the secret values.
    """

    missing = []

    if not GMAIL_CLIENT_ID:
        missing.append("GMAIL_CLIENT_ID")

    if not GMAIL_CLIENT_SECRET:
        missing.append("GMAIL_CLIENT_SECRET")

    if not GMAIL_REFRESH_TOKEN:
        missing.append("GMAIL_REFRESH_TOKEN")

    if not GMAIL_SENDER_EMAIL:
        missing.append("GMAIL_SENDER_EMAIL")

    if missing:
        raise RuntimeError(
            "Gmail environment variables are missing: "
            + ", ".join(missing)
        )


# ======================================================
# LOAD GMAIL OAUTH CREDENTIALS
# ======================================================

def _load_gmail_credentials():
    """
    Create Gmail OAuth credentials directly from Railway
    environment variables.

    No credentials.json.
    No token.json.
    No local browser authorization.
    """

    _validate_gmail_config()

    try:

        creds = Credentials(
            token=None,

            refresh_token=GMAIL_REFRESH_TOKEN,

            token_uri="https://oauth2.googleapis.com/token",

            client_id=GMAIL_CLIENT_ID,

            client_secret=GMAIL_CLIENT_SECRET,

            scopes=GMAIL_SCOPES
        )

        return creds

    except Exception as exc:

        raise RuntimeError(
            "Unable to create Gmail OAuth credentials "
            "from environment variables."
        ) from exc


# ======================================================
# GET GMAIL SERVICE
# ======================================================

def get_gmail_service():
    """
    Return an authenticated Gmail API service.

    The Gmail API client automatically uses the refresh
    token to obtain an access token when necessary.
    """

    creds = _load_gmail_credentials()

    return build(
        "gmail",
        "v1",
        credentials=creds,
        cache_discovery=False
    )


# ======================================================
# SEND EMAIL THROUGH GMAIL
# ======================================================

def send_gmail(
    recipient_email: str,
    subject: str,
    html_body: str | None = None,
    plain_body: str | None = None,
    reply_to: str | None = None,
    attachments: list[dict] | None = None
):
    """
    Send an email through the Gmail API.

    Sender:
        GMAIL_SENDER_EMAIL

    Recipient:
        recipient_email

    No Resend.
    No custom domain.
    No credentials.json.
    No token.json.
    """

    # --------------------------------------------------
    # CLEAN INPUT
    # --------------------------------------------------

    recipient_email = str(
        recipient_email or ""
    ).strip()


    subject = str(
        subject or ""
    ).replace(
        "\r",
        " "
    ).replace(
        "\n",
        " "
    ).strip()


    # --------------------------------------------------
    # VALIDATE
    # --------------------------------------------------

    if not recipient_email:

        raise ValueError(
            "Recipient email is empty."
        )


    if not subject:

        raise ValueError(
            "Email subject is empty."
        )


    _validate_gmail_config()


    # --------------------------------------------------
    # DEFAULT PLAIN TEXT
    # --------------------------------------------------

    if plain_body is None:

        plain_body = (
            "This email contains HTML content. "
            "Please use an HTML-compatible email client."
        )


    if html_body is None:

        html_body = ""


    # --------------------------------------------------
    # CREATE MIME MESSAGE
    # --------------------------------------------------

    message = MIMEMultipart("mixed")

    message["To"] = recipient_email
    message["From"] = (
        f"{GMAIL_FROM_NAME} "
        f"<{GMAIL_SENDER_EMAIL}>"
    )
    message["Subject"] = subject

    if reply_to:
        message["Reply-To"] = str(reply_to).strip()

    related = MIMEMultipart("related")
    alternative = MIMEMultipart("alternative")

    alternative.attach(
        MIMEText(str(plain_body), "plain", "utf-8")
    )

    if html_body:
        alternative.attach(
            MIMEText(str(html_body), "html", "utf-8")
        )

    related.attach(alternative)

    # Inline images used by the HTML email.
    for attachment in attachments or []:
        if not attachment.get("inline"):
            continue

        content = attachment.get("content")
        if not content:
            continue

        mime_type = str(
            attachment.get("mime_type", "image/png")
        ).lower()

        if mime_type == "image/png":
            image = MIMEImage(content, _subtype="png")
        elif mime_type == "image/jpeg":
            image = MIMEImage(content, _subtype="jpeg")
        else:
            continue

        content_id = attachment.get("content_id")
        if content_id:
            image.add_header("Content-ID", f"<{content_id}>")

        image.add_header(
            "Content-Disposition",
            "inline",
            filename=attachment.get("filename", "image.png")
        )
        related.attach(image)

    message.attach(related)

    # Downloadable attachments shown by Gmail.
    for attachment in attachments or []:
        if attachment.get("inline"):
            continue

        content = attachment.get("content")
        if not content:
            continue

        mime_type = str(
            attachment.get("mime_type", "application/octet-stream")
        )
        maintype, subtype = (
            mime_type.split("/", 1)
            if "/" in mime_type
            else ("application", "octet-stream")
        )

        if maintype == "image":
            part = MIMEImage(content, _subtype=subtype)
        else:
            from email.mime.base import MIMEBase
            from email import encoders
            part = MIMEBase(maintype, subtype)
            part.set_payload(content)
            encoders.encode_base64(part)

        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=attachment.get("filename", "attachment")
        )
        message.attach(part)


    # --------------------------------------------------
    # ENCODE MESSAGE
    # --------------------------------------------------

    raw_message = (
        base64.urlsafe_b64encode(
            message.as_bytes()
        )
        .decode("utf-8")
    )


    # --------------------------------------------------
    # SEND THROUGH GMAIL API
    # --------------------------------------------------

    try:

        service = get_gmail_service()


        result = (
            service
            .users()
            .messages()
            .send(
                userId="me",
                body={
                    "raw": raw_message
                }
            )
            .execute()
        )


    except Exception as exc:

        print(
            "GMAIL SEND ERROR:",
            repr(exc)
        )

        raise RuntimeError(
            f"Unable to send Gmail message: {exc}"
        ) from exc


    # --------------------------------------------------
    # RETURN RESULT
    # --------------------------------------------------

    return {

        "success": True,

        "provider": "gmail_api",

        "sender":
            GMAIL_SENDER_EMAIL,

        "recipient":
            recipient_email,

        "subject":
            subject,

        "message_id":
            result.get("id")

    }


# ======================================================
# ASYNC GMAIL SENDER
# ======================================================

async def send_gmail_async(
    recipient_email: str,
    subject: str,
    html_body: str | None = None,
    plain_body: str | None = None,
    reply_to: str | None = None,
    attachments: list[dict] | None = None
):
    """
    Async Gmail API sender.

    Gmail's Python client is synchronous, so the actual
    send operation runs in a worker thread so that it does
    not block FastAPI.
    """

    return await asyncio.to_thread(
        send_gmail,
        recipient_email,
        subject,
        html_body,
        plain_body,
        reply_to,
        attachments
    )


def send_gmail_smtp(
    recipient_email,
    subject,
    text_body=None,
    html_body=None,
    reply_to=None,
    attachments=None
):
    """
    Backward-compatible function name.

    This no longer uses SMTP. It sends through the Gmail API.
    """

    return send_gmail(
        recipient_email,
        subject,
        html_body=html_body,
        plain_body=text_body,
        reply_to=reply_to,
        attachments=attachments
    )







# ==========================================================
# ASYNC GMAIL SMTP SENDER
# ==========================================================


async def send_gmail_smtp_async(
    recipient_email,
    subject,
    text_body=None,
    html_body=None,
    reply_to=None,
    attachments=None
):
    """
    Backward-compatible async function name.

    This no longer uses SMTP. It sends through the Gmail API.
    """

    return await send_gmail_async(
        recipient_email,
        subject,
        html_body=html_body,
        plain_body=text_body,
        reply_to=reply_to,
        attachments=attachments
    )








# ==========================================================
# SEND CONTACT EMAIL
# ==========================================================

def send_contact_email(
    contact: ContactRequest
):

    # ------------------------------------------------------
    # Check Gmail configuration
    # ------------------------------------------------------

    if not GMAIL_SENDER_EMAIL:
        raise RuntimeError(
            "GMAIL_SENDER_EMAIL is not configured."
        )

    if not CONTACT_RECEIVER_EMAIL:
        raise RuntimeError(
            "CONTACT_RECEIVER_EMAIL is not configured."
        )


    # ------------------------------------------------------
    # Clean user input
    # ------------------------------------------------------

    name = contact.name.strip()

    sender_email = contact.email.strip()

    subject = contact.subject.strip()

    message = contact.message.strip()


    # ------------------------------------------------------
    # Prevent header injection
    # ------------------------------------------------------

    subject = (
        subject
        .replace("\r", " ")
        .replace("\n", " ")
    )

    name = (
        name
        .replace("\r", " ")
        .replace("\n", " ")
    )


    # ------------------------------------------------------
    # Create HTML email
    # ------------------------------------------------------

    email_html = f"""
    <html>

        <body>

            <h2>Contact Us Message</h2>

            <hr>

            <p>
                <strong>Name:</strong>
                {name}
            </p>

            <p>
                <strong>Email:</strong>
                {sender_email}
            </p>

            <p>
                <strong>Subject:</strong>
                {subject}
            </p>

            <p>
                <strong>Message:</strong>
            </p>

            <p>
                {message}
            </p>

            <hr>

            <p>
                This message was submitted through the
                CYF Registration System Contact Us form.
            </p>

        </body>

    </html>
    """


    # ------------------------------------------------------
    # Send email through Gmail SMTP
    # ------------------------------------------------------

    # ------------------------------------------------------
    # SEND THROUGH GMAIL SMTP
    # ------------------------------------------------------

    response = send_gmail_smtp(
        CONTACT_RECEIVER_EMAIL,
        f"Contact Us Message - {subject}",
        text_body=(
            f"Name: {name}\n"
            f"Email: {sender_email}\n"
            f"Subject: {subject}\n\n"
            f"Message:\n{message}\n\n"
            "This message was submitted through the "
            "CYF Registration System Contact Us form."
        ),
        html_body=email_html,
        reply_to=sender_email
    )


    # ------------------------------------------------------
    # Log successful email
    # ------------------------------------------------------

    print(
        "CONTACT EMAIL SENT SUCCESSFULLY:"
    )

    print(
        response
    )


    return response

# ======================================================
# SEND PAYMENT EMAIL
# ======================================================

async def send_payment_email(
    participant,
    event,
    payment
):

    # --------------------------------------------------
    # CHECK EMAIL
    # --------------------------------------------------

    if not participant.email:

        print(
            f"WARNING: Participant "
            f"{participant.id} has no email address."
        )

        return False

    # --------------------------------------------------
    # FORMAT INFORMATION
    # --------------------------------------------------

    fullname = (
        f"{participant.fname} "
        f"{participant.mname or ''} "
        f"{participant.lname}"
    ).strip()

    amount_display = (
        f"₱{payment.amount / 100:,.2f}"
    )

    # --------------------------------------------------
    # EMAIL SUBJECT
    # --------------------------------------------------

    subject = (
        f"Payment Instructions - "
        f"{event.event_name}"
    )

    # --------------------------------------------------
    # EMAIL HTML
    # --------------------------------------------------

    html = f"""
    <!DOCTYPE html>

    <html>

    <head>

        <meta charset="UTF-8">

        <meta name="viewport"
              content="width=device-width, initial-scale=1.0">

        <title>Payment Instructions</title>

    </head>

    <body style="
        margin:0;
        padding:0;
        background:#f5f5f5;
        font-family:Arial,Helvetica,sans-serif;
    ">

        <div style="
            max-width:650px;
            margin:30px auto;
            background:white;
            border-radius:12px;
            overflow:hidden;
            box-shadow:0 4px 20px rgba(0,0,0,0.08);
        ">

            <!-- HEADER -->

            <div style="
                background:#9d0b0b;
                color:white;
                padding:30px;
                text-align:center;
            ">

                <h1 style="
                    margin:0;
                    font-size:28px;
                ">
                    Event Registration
                </h1>

                <p style="
                    margin:8px 0 0;
                    color:#f5d27a;
                    font-size:16px;
                ">
                    Payment Instructions
                </p>

            </div>


            <!-- CONTENT -->

            <div style="padding:30px;">

                <h2 style="
                    color:#9d0b0b;
                    margin-top:0;
                ">
                    Hello {fullname}!
                </h2>

                <p style="
                    color:#444;
                    line-height:1.7;
                ">
                    Thank you for registering for
                    <strong>{event.event_name}</strong>.
                </p>

                <p style="
                    color:#444;
                    line-height:1.7;
                ">
                    Your registration has been successfully
                    recorded. Your payment is currently
                    <strong>Pending</strong>.
                </p>


                <!-- REGISTRATION DETAILS -->

                <div style="
                    background:#fff8e5;
                    border-left:5px solid #d4af37;
                    padding:20px;
                    margin:25px 0;
                    border-radius:6px;
                ">

                    <h3 style="
                        margin-top:0;
                        color:#9d0b0b;
                    ">
                        Registration Details
                    </h3>

                    <p>
                        <strong>Registration Number:</strong><br>
                        {participant.registration_number}
                    </p>

                    <p>
                        <strong>Participant:</strong><br>
                        {fullname}
                    </p>

                    <p>
                        <strong>Event:</strong><br>
                        {event.event_name}
                    </p>

                    <p>
                        <strong>Amount Due:</strong><br>

                        <span style="
                            font-size:24px;
                            font-weight:bold;
                            color:#9d0b0b;
                        ">
                            {amount_display}
                        </span>
                    </p>

                </div>


                <!-- PAY BUTTON -->

                <div style="
                    text-align:center;
                    margin:35px 0;
                ">

                    <a href="{payment.checkout_url}"
                       style="
                            display:inline-block;
                            background:#9d0b0b;
                            color:white;
                            text-decoration:none;
                            padding:15px 30px;
                            border-radius:8px;
                            font-weight:bold;
                            font-size:16px;
                       ">

                        PAY NOW

                    </a>

                </div>


                <p style="
                    color:#666;
                    font-size:14px;
                    line-height:1.6;
                ">

                    Please click the
                    <strong>PAY NOW</strong>
                    button above to continue to the
                    secure PayMongo checkout page.

                </p>


                <!-- IMPORTANT -->

                <div style="
                    background:#f8f8f8;
                    padding:15px;
                    border-radius:6px;
                    margin-top:25px;
                ">

                    <p style="
                        margin:0;
                        font-size:13px;
                        color:#666;
                    ">

                        <strong>Important:</strong>
                        Your registration will remain pending
                        until the payment has been successfully
                        confirmed.

                    </p>

                </div>

            </div>


            <!-- FOOTER -->

            <div style="
                background:#9d0b0b;
                color:white;
                text-align:center;
                padding:20px;
                font-size:13px;
            ">

                <p style="margin:0;">
                    Event Registration System
                </p>

                <p style="
                    margin:8px 0 0;
                    color:#f5d27a;
                ">
                    Please keep your registration number
                    for future reference.
                </p>

            </div>

        </div>

    </body>

    </html>
    """
    # --------------------------------------------------
    # SEND THROUGH GMAIL API
    # --------------------------------------------------

    try:

        await send_gmail_async(
            participant.email,
            subject,
            html_body=html
        )

        print(
            f"Payment email sent to "
            f"{participant.email}"
        )

        return True

    except Exception as e:

        print(
            f"ERROR sending payment email: {e}"
        )

        return False

# ======================================================
# PAYMENT CONFIRMATION EMAIL
# ======================================================


# ============================================================
# CYF EMAIL HELPERS
# ============================================================

MANILA_TZ = ZoneInfo("Asia/Manila")


def manila_timestamp(value=None):
    """Return a consistent Manila/PHT timestamp for all emails."""
    if value is None:
        value = datetime.datetime.now(datetime.timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(MANILA_TZ).strftime("%B %d, %Y • %I:%M %p (PHT)")


def _email_escape(value):
    import html
    return html.escape(str(value if value is not None else "N/A"))


def _email_logo_attachment():
    logo_path = os.path.join(WEB_DIR, "assets", "favicon.png")
    if not os.path.isfile(logo_path):
        return None, ""
    try:
        with open(logo_path, "rb") as f:
            data = f.read()
        return data, ('<img src="cid:cyf-logo" alt="CYF" width="58" '
                      'style="display:block;border:0;max-width:58px;">')
    except Exception as e:
        print("CYF email logo read failed:", repr(e))
        return None, ""


def _cyf_email_html(title, subtitle, greeting, intro, sections, notice=None, qr_html=None):
    logo_bytes, logo_html = _email_logo_attachment()
    section_html = ""
    for heading, rows in sections:
        row_html = ""
        for label, value in rows:
            row_html += f"""<tr><td style="padding:12px 16px;border-bottom:1px solid #eee;color:#777;width:42%;">{_email_escape(label)}</td><td style="padding:12px 16px;border-bottom:1px solid #eee;text-align:right;font-weight:600;word-break:break-word;">{_email_escape(value)}</td></tr>"""
        section_html += f"""<div style="border:1px solid #dedede;border-radius:10px;overflow:hidden;margin-bottom:22px;"><div style="background:#fafafa;padding:13px 16px;border-bottom:1px solid #dedede;color:#9d0b0b;font-weight:800;font-size:13px;letter-spacing:.5px;">{_email_escape(heading).upper()}</div><table style="width:100%;border-collapse:collapse;">{row_html}</table></div>"""
    notice_html = ""
    if notice:
        notice_html = f"""<div style="background:#fff8e5;border-left:4px solid #d4af37;padding:15px 16px;border-radius:7px;margin:24px 0;color:#555;line-height:1.6;font-size:13px;">{notice}</div>"""
    qr_block = qr_html or ""
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head><body style="margin:0;padding:0;background:#f1f3f5;font-family:Arial,Helvetica,sans-serif;color:#222;"><div style="width:100%;padding:35px 10px;background:#f1f3f5;"><div style="max-width:680px;margin:0 auto;background:#fff;border:1px solid #e3e3e3;border-radius:14px;overflow:hidden;"><div style="background:#9d0b0b;padding:24px 30px;color:#fff;"><table style="width:100%;border-collapse:collapse;"><tr><td style="vertical-align:middle;width:70px;">{logo_html}</td><td style="vertical-align:middle;text-align:right;"><div style="font-size:11px;color:#f5d27a;letter-spacing:1px;font-weight:bold;">CARAGA YOUTH FELLOWSHIP</div><div style="font-size:25px;font-weight:800;margin-top:5px;">{_email_escape(title)}</div><div style="font-size:12px;color:#f8dddd;margin-top:5px;">{_email_escape(subtitle)}</div></td></tr></table></div><div style="margin:24px 30px 0;padding:13px 18px;background:#eaf7ee;border:1px solid #bfe4ca;border-radius:9px;color:#16803c;font-weight:bold;text-align:center;">✓ CONFIRMATION SUCCESSFUL</div><div style="padding:28px 30px 32px;"><p style="margin:0 0 8px;color:#555;font-size:15px;">Dear {_email_escape(greeting)},</p><p style="margin:0 0 24px;color:#555;line-height:1.7;font-size:14px;">{intro}</p>{section_html}{qr_block}{notice_html}<p style="margin:24px 0 0;color:#666;line-height:1.7;font-size:13px;">Please keep this email for your records. Payment times shown in this receipt are in Manila time (PHT, UTC+8).</p></div><div style="background:#9d0b0b;color:#fff;padding:22px 30px;text-align:center;"><div style="font-size:15px;font-weight:700;">CYF Registration System</div><div style="margin-top:6px;color:#f5d27a;font-size:12px;">Thank you for being part of CYF.</div></div></div></div></body></html>"""
    return html, logo_bytes


def _plain_from_sections(title, greeting, intro, sections, timestamp=None):
    lines=[title, "", f"Dear {greeting},", "", re.sub('<[^>]+>', '', intro)]
    for heading, rows in sections:
        lines += ["", heading.upper()]
        for label, value in rows:
            lines.append(f"{label}: {value}")
    if timestamp:
        lines += ["", f"Date/Time: {timestamp}"]
    return "\n".join(lines)

async def send_payment_confirmation_email(participant, payment):
    """Professional participant payment confirmation; never includes a QR code."""
    try:
        email = str(getattr(participant, "email", "") or "").strip()
        if not email:
            print("Participant payment confirmation skipped: email is empty.")
            return False
        name = (f"{getattr(participant,'fname','') or ''} {getattr(participant,'mname','') or ''} {getattr(participant,'lname','') or ''}").replace("  ", " ").strip() or "Participant"
        amount = Decimal(str(getattr(payment,"amount",0) or 0))/Decimal("100")
        reference = getattr(payment,"paymongo_reference",None) or getattr(payment,"paymongo_payment_id",None) or "N/A"
        paid_at = getattr(payment,"paid_at",None) or getattr(payment,"created_at",None)
        timestamp = manila_timestamp(paid_at)
        items=[]
        if getattr(payment,"tshirt_selected",0):
            size=getattr(payment,"tshirt_size",None)
            items.append(f"T-Shirt ({size})" if size else "T-Shirt")
        if getattr(payment,"lanyard_selected",0): items.append("Lanyard")
        if not items: items=["Registration Payment"]
        sections=[("Registration Details", [("Registration Number",getattr(participant,"registration_number","N/A")),("Participant",name)]),
                  ("Payment Details", [("Payment Date",timestamp),("PayMongo Reference",reference),("Payment Status","PAID"),("Amount Paid",f"₱{amount:,.2f}")]),
                  ("Items Paid", [("Items",", ".join(items))])]
        html_body, logo_bytes = _cyf_email_html("PAYMENT CONFIRMATION","CYF Registration System",name,"Your participant payment has been successfully confirmed.",sections,notice="This confirmation does not contain a participant QR code. The QR code is issued only with the lanyard receipt.")
        attachments=[]
        if logo_bytes: attachments.append({"filename":"favicon.png","content":logo_bytes,"mime_type":"image/png","content_id":"cyf-logo","inline":True})
        plain=_plain_from_sections("CYF PAYMENT CONFIRMATION",name,"Your participant payment has been successfully confirmed.",sections)
        await send_gmail_async(email,f"Payment Confirmed • {getattr(participant,'registration_number','CYF')}",html_body=html_body,plain_body=plain,attachments=attachments)
        print("PARTICIPANT PAYMENT CONFIRMATION SENT", email)
        return True
    except Exception as e:
        print("PARTICIPANT PAYMENT CONFIRMATION FAILED:",repr(e))
        return False













# ============================================================
# ITEM SPONSORSHIP CONFIRMATION EMAIL
# ============================================================

async def send_item_sponsorship_confirmation_email(donation):
    """Professional item-donation confirmation; never includes a QR code."""
    try:
        email=str(getattr(donation,"email","") or "").strip()
        if not email: return False
        name=getattr(donation,"sponsor_name",None) or "Sponsor"
        qty=getattr(donation,"quantity",0) or 0
        unit=getattr(donation,"unit",None) or "unit"
        timestamp=manila_timestamp(getattr(donation,"created_at",None))
        sections=[("Sponsor Details",[("Sponsor Name",name),("Local Church",getattr(donation,"local_church","N/A")),("Contact Number",getattr(donation,"contact","N/A")),("Sector",getattr(donation,"sector","N/A"))]),
                  ("Donation Details",[("Item Donated",getattr(donation,"item_name","Item")),("Quantity",f"{qty} {unit}"),("Donation Status","CONFIRMED"),("Confirmation Date",timestamp)]),
                  ("Delivery Information",[("Delivery Location","Butuan Grace Baptist Church"),("Contact Person","Pastor Edward Deligero"),("Contact Number","0911 252 3584")])]
        html,logo=_cyf_email_html("ITEM DONATION CONFIRMATION","CYF Registration System",name,"Thank you for your generous support of the CYF ministry. Your item donation sponsorship has been successfully recorded.",sections,notice="Your contribution will help provide the necessary resources and materials for CYF youth ministry activities. Thank you for your generosity.")
        att=[]
        if logo: att.append({"filename":"favicon.png","content":logo,"mime_type":"image/png","content_id":"cyf-logo","inline":True})
        await send_gmail_async(email,"Item Donation Sponsorship Confirmation • CYF",html_body=html,plain_body=_plain_from_sections("CYF ITEM DONATION CONFIRMATION",name,"Your item donation sponsorship has been successfully recorded.",sections),attachments=att)
        print("ITEM SPONSORSHIP CONFIRMATION SENT",email)
        return True
    except Exception as e:
        print("ITEM SPONSORSHIP CONFIRMATION FAILED:",repr(e)); return False




# ======================================================
# FINDING SPONSOR - PARTICIPANT EMAIL
# ======================================================
#
# Sent automatically when a cash donation successfully
# sponsors a Finding Sponsor participant.
#
# The email is sent to the PARTICIPANT.
#
# It informs them that:
#
# - Registration is complete
# - Sponsor review is approved
# - T-shirt is paid
# - Lanyard is paid
#
# ======================================================

async def send_sponsored_participant_confirmation_email(participant, sponsored_amount):
    """Professional sponsored-participant approval; never includes a QR code."""
    try:
        email=str(getattr(participant,"email","") or "").strip()
        if not email: return False
        name=(f"{getattr(participant,'fname','') or ''} {getattr(participant,'mname','') or ''} {getattr(participant,'lname','') or ''}").replace("  "," ").strip() or "Participant"
        amount=Decimal(str(sponsored_amount or 0))
        timestamp=manila_timestamp()
        sections=[("Registration Details",[("Participant",name),("Registration Number",getattr(participant,"registration_number","N/A")),("Registration Status","COMPLETE"),("Sponsor Review","APPROVED"),("Sponsored Amount",f"₱{amount:,.2f}"),("Confirmation Date",timestamp)]),
                  ("Merchandise Status",[("T-Shirt",getattr(participant,"tshirt_status","PAID") or "PAID"),("Lanyard",getattr(participant,"lanyard_status","PAID") or "PAID")])]
        html,logo=_cyf_email_html("REGISTRATION COMPLETED","CYF Registration System",name,"Congratulations! Your registration has been successfully completed through the sponsorship program.",sections,notice="No additional payment is required for the sponsored T-shirt and lanyard. Your registration has already been completed through sponsorship.")
        att=[]
        if logo: att.append({"filename":"favicon.png","content":logo,"mime_type":"image/png","content_id":"cyf-logo","inline":True})
        await send_gmail_async(email,f"Registration Completed Through Sponsorship • {getattr(participant,'registration_number','CYF')}",html_body=html,plain_body=_plain_from_sections("CYF SPONSORED REGISTRATION CONFIRMATION",name,"Your registration has been successfully completed through sponsorship.",sections),attachments=att)
        print("SPONSORED PARTICIPANT CONFIRMATION SENT",email); return True
    except Exception as e:
        print("SPONSORED PARTICIPANT CONFIRMATION FAILED:",repr(e)); return False












# ======================================================
# SEND SPONSOR CONFIRMATION EMAIL
# ======================================================

async def send_sponsor_confirmation_email(sponsor, payment):
    """Professional sponsor payment confirmation; never includes a QR code."""
    try:
        email=str(getattr(sponsor,"email","") or "").strip()
        if not email: return False
        name=getattr(sponsor,"fname",None) or "Sponsor"
        amount=Decimal(str(getattr(payment,"amount",0) or 0))/Decimal("100")
        timestamp=manila_timestamp(getattr(payment,"paid_at",None) or getattr(payment,"created_at",None))
        sections=[("Sponsorship Details",[("Sponsor Name",name),("Sponsorship Tier",getattr(payment,"sponsorship_tier",None) or "Sponsorship"),("Donation Amount",f"₱{amount:,.2f}"),("Payment Status","PAID"),("PayMongo Reference",getattr(payment,"paymongo_reference",None) or "N/A"),("Payment Date",timestamp)])]
        html,logo=_cyf_email_html("SPONSORSHIP CONFIRMATION","CYF Registration System",name,"Thank you for your generous donation. Your sponsorship payment has been successfully received.",sections,notice="Your support helps sustain CYF events and youth ministry activities. We sincerely appreciate your generosity.")
        att=[]
        if logo: att.append({"filename":"favicon.png","content":logo,"mime_type":"image/png","content_id":"cyf-logo","inline":True})
        await send_gmail_async(email,"CYF Sponsorship Donation Confirmation",html_body=html,plain_body=_plain_from_sections("CYF SPONSORSHIP CONFIRMATION",name,"Your sponsorship payment has been successfully received.",sections),attachments=att)
        print("SPONSOR CONFIRMATION SENT",email); return True
    except Exception as e:
        print("SPONSOR CONFIRMATION FAILED:",repr(e)); return False


# ============================================================
# PARTICIPANT PAYMENT CONFIRMATION EMAIL
# ============================================================

async def send_participant_payment_confirmation_email(participant, payment):
    """Send the only CYF email that contains a participant QR code: lanyard receipt."""
    try:
        if str(getattr(participant,"lanyard_status","") or "").strip().lower() != "paid":
            print("Participant QR receipt skipped: lanyard is not Paid."); return False
        if bool(getattr(payment,"receipt_sent",False)):
            print("Participant QR receipt already sent:",getattr(participant,"id",None)); return True
        email=str(getattr(participant,"email","") or "").strip()
        reg=str(getattr(participant,"registration_number","") or "").strip()
        if not email or not reg: return False
        name=(f"{getattr(participant,'fname','') or ''} {getattr(participant,'mname','') or ''} {getattr(participant,'lname','') or ''}").replace("  "," ").strip() or "Participant"
        amount=Decimal(str(getattr(payment,"amount",0) or 0))/Decimal("100")
        reference=getattr(payment,"paymongo_reference",None) or getattr(payment,"paymongo_payment_id",None) or "N/A"
        timestamp=manila_timestamp(getattr(payment,"paid_at",None) or getattr(payment,"created_at",None))
        items=[]
        if getattr(payment,"tshirt_selected",0):
            size=getattr(payment,"tshirt_size",None); items.append(f"T-Shirt ({size})" if size else "T-Shirt")
        if getattr(payment,"lanyard_selected",0): items.append("Lanyard")
        if not items: items=["Lanyard"]
        sections=[("Registration Details",[("Registration Number",reg),("Participant",name),("Event",getattr(participant,"event_name","CYF Event") or "CYF Event")]),
                  ("Payment Details",[("Payment Date",timestamp),("PayMongo Reference",reference),("Payment Status","PAID"),("Amount Paid",f"₱{amount:,.2f}")]),
                  ("Items Paid",[("Items",", ".join(items))])]
        qr_bytes=generate_participant_qr(reg)
        qr_html=f"""<div style="border:2px solid #9d0b0b;border-radius:12px;padding:24px 18px;text-align:center;margin:28px 0;background:#fff;"><div style="color:#9d0b0b;font-size:18px;font-weight:800;margin-bottom:7px;">YOUR PARTICIPANT QR CODE</div><p style="margin:0 0 18px;color:#666;font-size:13px;line-height:1.5;">Present this QR code during registration/check-in.</p><img src="cid:participant-qrcode" alt="Participant QR Code" width="220" height="220" style="display:block;width:220px;height:220px;margin:0 auto;border:1px solid #ddd;"><div style="margin-top:15px;display:inline-block;padding:9px 16px;background:#f7f7f7;border-radius:7px;font-size:16px;font-weight:800;letter-spacing:1px;color:#222;">{_email_escape(reg)}</div><p style="margin:15px 0 0;color:#777;font-size:12px;">A downloadable PNG copy is attached to this email.</p></div>"""
        html,logo=_cyf_email_html("LANYARD PAYMENT RECEIPT","CYF Registration System",name,"Thank you for completing your lanyard payment. This email serves as your official CYF lanyard payment receipt.",sections,notice="Keep this receipt safe. Your QR code contains your registration number and may be used by the CYF Registration Team to identify your registration.",qr_html=qr_html)
        attachments=[{"filename":f"{reg}_QR.png","content":qr_bytes,"mime_type":"image/png","inline":False},{"filename":"participant_qrcode.png","content":qr_bytes,"mime_type":"image/png","content_id":"participant-qrcode","inline":True}]
        if logo: attachments.append({"filename":"favicon.png","content":logo,"mime_type":"image/png","content_id":"cyf-logo","inline":True})
        plain=_plain_from_sections("CYF LANYARD PAYMENT RECEIPT",name,"Your lanyard payment has been successfully confirmed.",sections)
        plain += f"\n\nQR code attached: {reg}_QR.png\n"
        await send_gmail_async(email,f"Lanyard Payment Receipt • {reg} • CYF",html_body=html,plain_body=plain,attachments=attachments)
        payment.receipt_sent=True
        try:
            sess=object_session(payment)
            if sess: sess.commit()
        except Exception as e: print("WARNING: QR receipt sent but receipt_sent could not be saved:",repr(e))
        print("PARTICIPANT LANYARD QR RECEIPT SENT",email,reg,f"{reg}_QR.png")
        return True
    except Exception as e:
        print("PARTICIPANT LANYARD QR RECEIPT FAILED:",repr(e)); return False





# ============================================================
# STORE PAYMENT RECEIPT EMAIL
# ============================================================

async def send_store_payment_receipt_email(store_payments, store_order_id=None):
    """Send one professional Gmail receipt per paid store order; never includes a QR code."""
    try:
        if not store_payments:
            print("STORE RECEIPT EMAIL SKIPPED: no payment rows")
            return False
        paid_rows=[p for p in store_payments if str(getattr(p,"status","") or "").strip().lower()=="paid"]
        if not paid_rows: return False
        order_id=str(store_order_id or getattr(paid_rows[0],"store_order_id","") or "N/A")
        recipient=str(getattr(paid_rows[0],"customer_email","") or "").strip()
        name=str(getattr(paid_rows[0],"customer_name","") or "Customer").strip() or "Customer"
        if not recipient:
            print("STORE RECEIPT EMAIL FAILED: customer email is empty",order_id); return False
        # If every row is already marked sent, this webhook is a duplicate.
        if all(bool(getattr(p,"receipt_sent",False)) for p in paid_rows):
            print("STORE RECEIPT EMAIL ALREADY SENT:",order_id); return True
        total=Decimal("0")
        item_rows=[]
        latest_date=None
        for p in paid_rows:
            amount=Decimal(str(getattr(p,"amount",0) or 0))/Decimal("100")
            total += amount
            paid_at=getattr(p,"paid_at",None) or getattr(p,"created_at",None)
            if paid_at and (latest_date is None or paid_at>latest_date): latest_date=paid_at
            item_id=getattr(p,"store_item_id",None)
            item_name="Store Item"
            try:
                sess=object_session(p)
                if sess and item_id:
                    item=sess.query(StoreItem).filter(StoreItem.id==item_id).first()
                    if item: item_name=getattr(item,"item_name",None) or item_name
            except Exception as e: print("STORE RECEIPT ITEM LOOKUP FAILED:",repr(e))
            qty=getattr(p,"store_quantity",1) or 1
            size=getattr(p,"store_size",None)
            label=f"{item_name} × {qty}" + (f" ({size})" if size else "")
            item_rows.append((label,f"₱{amount:,.2f}"))
        timestamp=manila_timestamp(latest_date)
        sections=[("Order Details",[("Order ID",order_id),("Customer",name),("Payment Date",timestamp),("Payment Status","PAID"),("PayMongo Reference",getattr(paid_rows[0],"paymongo_reference",None) or getattr(paid_rows[0],"paymongo_payment_id",None) or "N/A")]),
                  ("Items Purchased",[(label,amount) for label,amount in item_rows]),
                  ("Order Total",[("TOTAL PAID",f"₱{total:,.2f}")])]
        html,logo=_cyf_email_html("STORE PAYMENT RECEIPT","CYF Registration System",name,"Thank you for your purchase. Your store payment has been successfully confirmed.",sections,notice="Please keep this receipt for your records. Your order is marked as PAID in the CYF Registration System.")
        att=[]
        if logo: att.append({"filename":"favicon.png","content":logo,"mime_type":"image/png","content_id":"cyf-logo","inline":True})
        plain=_plain_from_sections("CYF STORE PAYMENT RECEIPT",name,"Your store payment has been successfully confirmed.",sections)
        await send_gmail_async(recipient,f"Store Payment Receipt • {order_id} • CYF",html_body=html,plain_body=plain,attachments=att)
        for p in paid_rows: p.receipt_sent=True
        sess=object_session(paid_rows[0])
        if sess: sess.commit()
        print("STORE RECEIPT EMAIL SENT",recipient,"Order:",order_id,"Rows:",len(paid_rows),"Total:",f"₱{total:,.2f}")
        return True
    except Exception as e:
        print("STORE RECEIPT EMAIL FAILED:",repr(e))
        try:
            sess=object_session(store_payments[0]) if store_payments else None
            if sess: sess.rollback()
        except Exception: pass
        return False

async def send_cash_sponsorship_confirmation_email(sponsorship, payment):
    """Professional cash sponsorship confirmation; never includes a QR code."""
    try:
        email=str(getattr(sponsorship,"email","") or "").strip()
        if not email: return False
        name=getattr(sponsorship,"sponsor_name",None) or "Sponsor"
        tier=getattr(sponsorship,"selected_tier",None) or getattr(sponsorship,"package_tier",None) or "Sponsorship Package"
        raw=getattr(sponsorship,"donation_amount",None)
        if raw in (None, ""): raw=getattr(payment,"amount",0)
        amount=Decimal(str(raw or 0))/Decimal("100")
        reference=getattr(sponsorship,"paymongo_reference",None) or getattr(payment,"paymongo_reference",None) or "N/A"
        timestamp=manila_timestamp(getattr(payment,"paid_at",None) or getattr(sponsorship,"created_at",None))
        sections=[("Sponsorship Details",[("Sponsor Name",name),("Sponsorship Tier",tier),("Donation Amount",f"₱{amount:,.2f}"),("Payment Status",getattr(payment,"status","Paid") or "Paid"),("PayMongo Reference",reference),("Payment Date",timestamp)])]
        html,logo=_cyf_email_html("CASH SPONSORSHIP CONFIRMATION","CYF Registration System",name,"Your cash sponsorship payment has been successfully received.",sections,notice="Thank you for helping support CYF events and youth ministry activities. Your generosity is greatly appreciated.")
        att=[]
        if logo: att.append({"filename":"favicon.png","content":logo,"mime_type":"image/png","content_id":"cyf-logo","inline":True})
        await send_gmail_async(email,"Cash Sponsorship Payment Confirmation • CYF",html_body=html,plain_body=_plain_from_sections("CYF CASH SPONSORSHIP CONFIRMATION",name,"Your cash sponsorship payment has been successfully received.",sections),attachments=att)
        print("CASH SPONSORSHIP CONFIRMATION SENT",email); return True
    except Exception as e:
        print("CASH SPONSORSHIP CONFIRMATION FAILED:",repr(e)); return False
