import base64
import re
from io import BytesIO

import segno
from django.urls import reverse

from looplink.campaigns.exceptions import CampaignValidationError
from looplink.campaigns.models import IdentityType

# ─── Identity normalization ──────────────────────────────────────────────────
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PHONE_DIGITS = 10
MAX_PHONE_DIGITS = 10


def normalize_identity(raw_identity):
    raw = (raw_identity or "").strip()
    if not raw:
        raise CampaignValidationError({"identity": ["Enter a phone number or email address."]})

    is_email = "@" in raw
    if is_email:
        normalized = raw.lower()
        if not EMAIL_RE.match(normalized):
            raise CampaignValidationError({"identity": ["Enter a valid email address."]})
        return normalized, IdentityType.EMAIL

    digits = re.sub(r"\D", "", raw)
    if not (MIN_PHONE_DIGITS <= len(digits) <= MAX_PHONE_DIGITS):
        raise CampaignValidationError({"identity": ["Enter a valid phone number or email address."]})
    return digits, IdentityType.PHONE


# ─── Distribution link / QR ──────────────────────────────────────────────────
def distribution_path(campaign):
    return reverse("shopper_campaign", args=[campaign.token])


def distribution_url(request, campaign):
    return request.build_absolute_uri(distribution_path(campaign))


def qr_code_data_uri(url):
    """PNG data URI for the given URL, suitable for an inline <img src>."""
    buffer = BytesIO()
    segno.make(url, error="m").save(buffer, kind="png", scale=6, border=2)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
