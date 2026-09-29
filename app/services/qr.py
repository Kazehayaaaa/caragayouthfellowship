"""Participant QR code generation."""

from io import BytesIO
import qrcode

# ============================================================
# PARTICIPANT QR CODE GENERATOR
# ============================================================

def generate_participant_qr(registration_number: str) -> bytes:
    """
    Generate a PNG QR code containing the participant's
    registration number.

    Example payload:
        SYC-2026-0001
    """

    registration_number = str(
        registration_number or ""
    ).strip()

    if not registration_number:
        raise ValueError(
            "Registration number is required for QR generation."
        )

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=12,
        border=4
    )

    qr.add_data(registration_number)
    qr.make(fit=True)

    image = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    buffer = BytesIO()
    image.save(buffer, format="PNG")

    return buffer.getvalue()
