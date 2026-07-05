import re

from looplink.campaigns.exceptions import CampaignValidationError
from looplink.campaigns.models import IdentityType

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
