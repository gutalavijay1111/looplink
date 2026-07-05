import pytest
from django.test import RequestFactory

from looplink.campaigns.exceptions import CampaignValidationError
from looplink.campaigns.models import IdentityType
from looplink.campaigns.utilities import distribution_path, distribution_url, normalize_identity, qr_code_data_uri


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


@pytest.mark.django_db()
def test_distribution_path_encodes_token_not_pk(make_campaign):
    campaign = make_campaign()

    path = distribution_path(campaign)

    # Built from the token alone; asserting equality (rather than checking the
    # pk's digits happen not to appear in the random token) is what actually
    # proves the pk isn't part of the encoding.
    assert path == f"/c/{campaign.token}/"


@pytest.mark.django_db()
def test_distribution_url_is_absolute(make_campaign):
    campaign = make_campaign()
    request = RequestFactory().get("/")

    url = distribution_url(request, campaign)

    assert url == f"http://testserver/c/{campaign.token}/"


def test_qr_code_data_uri_is_a_png_data_uri():
    data_uri = qr_code_data_uri("http://testserver/c/abc123/")

    assert data_uri.startswith("data:image/png;base64,")
    assert len(data_uri) > len("data:image/png;base64,")
