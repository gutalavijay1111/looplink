import pytest

from looplink.campaigns.exceptions import CampaignValidationError
from looplink.campaigns.identity import normalize_identity
from looplink.campaigns.models import IdentityType


def test_normalizes_email_trim_and_lowercase():
    normalized, identity_type = normalize_identity("  Shopper@Example.COM  ")

    assert normalized == "shopper@example.com"
    assert identity_type == IdentityType.EMAIL


def test_normalizes_phone_strips_punctuation():
    normalized, identity_type = normalize_identity("(555) 123-4567")

    assert normalized == "5551234567"
    assert identity_type == IdentityType.PHONE


def test_rejects_blank_identity():
    with pytest.raises(CampaignValidationError):
        normalize_identity("   ")


def test_rejects_malformed_email():
    with pytest.raises(CampaignValidationError):
        normalize_identity("not-an-email")


def test_rejects_too_short_phone_number():
    with pytest.raises(CampaignValidationError):
        normalize_identity("123")
