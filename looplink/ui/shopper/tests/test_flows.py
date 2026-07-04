from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from looplink.campaigns.models import Campaign, CampaignStatus, Enrollment, Offer, OfferType

pytestmark = pytest.mark.django_db


def make_campaign(**kwargs):
    now = timezone.now()
    defaults = {
        "name": "Summer Sale",
        "description": "Seasonal offers",
        "starts_at": now,
        "ends_at": now + timedelta(days=7),
    }
    defaults.update(kwargs)
    return Campaign.objects.create(**defaults)


def campaign_url(campaign):
    return reverse("shopper_campaign", args=[campaign.token])


def htmx_post(client, url, action, data=None):
    return client.post(url, data or {}, HTTP_DJ_HX_ACTION=action)


def test_invalid_token_returns_404_with_friendly_copy(client):
    response = client.get(reverse("shopper_campaign", args=["does-not-exist"]))

    assert response.status_code == 404
    assert "Link not found" in response.content.decode()


@pytest.mark.parametrize(
    ("status", "expected_copy"),
    [
        (CampaignStatus.DRAFT, "isn't available yet"),
        (CampaignStatus.SCHEDULED, "hasn't started yet"),
        (CampaignStatus.ENDED, "has ended"),
    ],
)
def test_non_live_scan_shows_appropriate_state_and_no_offers(client, status, expected_copy):
    campaign = make_campaign(status=status)
    Offer.objects.create(campaign=campaign, offer_type=OfferType.STICKER_EARN, params={"stickers": 1, "per_amount": 10})

    response = client.get(campaign_url(campaign))

    content = response.content.decode()
    assert response.status_code == 200
    assert expected_copy in content
    assert "Get my offers" not in content
    assert "Sticker earn" not in content


def test_live_campaign_shows_offers_and_enroll_form(client):
    campaign = make_campaign(status=CampaignStatus.LIVE)
    Offer.objects.create(
        campaign=campaign,
        offer_type=OfferType.PRODUCT_PERCENT_DISCOUNT,
        params={"percent": 20, "applies_to": "Snacks"},
    )

    response = client.get(campaign_url(campaign))

    content = response.content.decode()
    assert "20% off Snacks" in content
    assert "Get my offers" in content


def test_enroll_with_valid_identity_creates_enrollment(client):
    campaign = make_campaign(status=CampaignStatus.LIVE)

    response = htmx_post(client, campaign_url(campaign), "enroll", {"identity": "shopper@example.com"})

    assert response.status_code == 200
    assert "You&#x27;re in!" in response.content.decode() or "You're in!" in response.content.decode()
    assert Enrollment.objects.filter(campaign=campaign, normalized_identity="shopper@example.com").exists()


def test_repeat_enrollment_is_recognized_not_duplicated(client):
    campaign = make_campaign(status=CampaignStatus.LIVE)

    htmx_post(client, campaign_url(campaign), "enroll", {"identity": "shopper@example.com"})
    response = htmx_post(client, campaign_url(campaign), "enroll", {"identity": "  SHOPPER@EXAMPLE.COM  "})

    content = response.content.decode()
    assert "Welcome back!" in content
    assert Enrollment.objects.filter(campaign=campaign).count() == 1


def test_enroll_with_invalid_identity_shows_inline_error(client):
    campaign = make_campaign(status=CampaignStatus.LIVE)

    response = htmx_post(client, campaign_url(campaign), "enroll", {"identity": "not-an-identity"})

    assert response.status_code == 200
    assert "Enter a valid phone number or email address." in response.content.decode()
    assert Enrollment.objects.count() == 0


def test_enroll_on_non_live_campaign_is_rejected_server_side(client):
    """
    Direct POST bypassing the UI (e.g. a stale tab after the campaign ended)
    must still be blocked — the server falls back to rendering the campaign's
    actual current state rather than creating an enrollment.
    """
    campaign = make_campaign(status=CampaignStatus.DRAFT)

    response = htmx_post(client, campaign_url(campaign), "enroll", {"identity": "shopper@example.com"})

    assert response.status_code == 200
    assert "isn't available yet" in response.content.decode()
    assert Enrollment.objects.count() == 0
