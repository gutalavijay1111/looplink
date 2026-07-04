from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from looplink.campaigns.models import Campaign, CampaignStatus, Offer, OfferType

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


def htmx_post(client, url, action, data=None):
    return client.post(url, data or {}, HTTP_DJ_HX_ACTION=action)


def test_new_campaign_creates_draft_and_redirects(client):
    response = client.post(reverse("builder_campaign_list"))

    assert response.status_code == 302
    campaign = Campaign.objects.get()
    assert campaign.status == CampaignStatus.DRAFT
    assert response.url == reverse("builder_campaign_detail", args=[campaign.pk])


def test_save_details_updates_draft(client):
    campaign = make_campaign()
    url = reverse("builder_campaign_detail", args=[campaign.pk])
    now = timezone.now()

    response = htmx_post(
        client,
        url,
        "save_details",
        {
            "expected_updated_at": campaign.updated_at.isoformat(),
            "name": "New name",
            "description": "New description",
            "starts_at": now.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": (now + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
        },
    )

    campaign.refresh_from_db()
    assert response.status_code == 200
    assert campaign.name == "New name"


def test_save_details_shows_inline_validation_error(client):
    campaign = make_campaign()
    url = reverse("builder_campaign_detail", args=[campaign.pk])

    response = htmx_post(
        client,
        url,
        "save_details",
        {
            "expected_updated_at": campaign.updated_at.isoformat(),
            "name": "",
            "description": "",
            "starts_at": "2026-01-01T00:00",
            "ends_at": "2026-01-02T00:00",
        },
    )

    assert response.status_code == 200
    assert "Name is required" in response.content.decode()


def test_add_offer_then_remove_offer(client):
    campaign = make_campaign()
    url = reverse("builder_campaign_detail", args=[campaign.pk])

    htmx_post(
        client,
        url,
        "add_offer",
        {
            "expected_updated_at": campaign.updated_at.isoformat(),
            "offer_type": OfferType.STICKER_EARN,
            "stickers": "1",
            "per_amount": "10",
        },
    )
    offer = Offer.objects.get(campaign=campaign)
    campaign.refresh_from_db()

    response = htmx_post(
        client,
        url,
        "remove_offer",
        {"expected_updated_at": campaign.updated_at.isoformat(), "offer_id": offer.pk},
    )

    assert response.status_code == 200
    assert not Offer.objects.filter(pk=offer.pk).exists()


def test_add_offer_with_invalid_params_shows_error_and_does_not_create(client):
    campaign = make_campaign()
    url = reverse("builder_campaign_detail", args=[campaign.pk])

    response = htmx_post(
        client,
        url,
        "add_offer",
        {
            "expected_updated_at": campaign.updated_at.isoformat(),
            "offer_type": OfferType.STICKER_EARN,
            "stickers": "0",
            "per_amount": "10",
        },
    )

    assert response.status_code == 200
    assert "Must be greater than 0" in response.content.decode()
    assert Offer.objects.count() == 0


def test_launch_blocked_without_offers_shows_error(client):
    campaign = make_campaign()
    url = reverse("builder_campaign_detail", args=[campaign.pk])

    response = htmx_post(client, url, "launch", {"expected_updated_at": campaign.updated_at.isoformat()})

    campaign.refresh_from_db()
    assert response.status_code == 200
    assert "Add at least one offer before launching" in response.content.decode()
    assert campaign.status == CampaignStatus.DRAFT


def test_launch_then_illegal_schedule_is_rejected_by_server(client):
    campaign = make_campaign()
    Offer.objects.create(campaign=campaign, offer_type=OfferType.STICKER_EARN, params={"stickers": 1, "per_amount": 10})
    url = reverse("builder_campaign_detail", args=[campaign.pk])

    htmx_post(client, url, "launch", {"expected_updated_at": campaign.updated_at.isoformat()})
    campaign.refresh_from_db()
    assert campaign.status == CampaignStatus.LIVE

    response = htmx_post(client, url, "schedule", {"expected_updated_at": campaign.updated_at.isoformat()})

    campaign.refresh_from_db()
    assert response.status_code == 200
    assert "not allowed from the campaign" in response.content.decode()
    assert campaign.status == CampaignStatus.LIVE


def test_stale_edit_is_rejected(client):
    """User A loads the draft; user B saves first; user A's stale save is rejected."""
    campaign = make_campaign()
    url = reverse("builder_campaign_detail", args=[campaign.pk])
    stale_updated_at = campaign.updated_at.isoformat()
    now = timezone.now()

    htmx_post(
        client,
        url,
        "save_details",
        {
            "expected_updated_at": stale_updated_at,
            "name": "B's edit",
            "description": "",
            "starts_at": now.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": (now + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
        },
    )

    response = htmx_post(
        client,
        url,
        "save_details",
        {
            "expected_updated_at": stale_updated_at,
            "name": "A's edit",
            "description": "",
            "starts_at": now.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": (now + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
        },
    )

    campaign.refresh_from_db()
    assert response.status_code == 200
    assert "changed since you loaded it" in response.content.decode()
    assert campaign.name == "B's edit"


def test_end_from_live_succeeds(client):
    campaign = make_campaign(status=CampaignStatus.LIVE)
    url = reverse("builder_campaign_detail", args=[campaign.pk])

    response = htmx_post(client, url, "end", {"expected_updated_at": campaign.updated_at.isoformat()})

    campaign.refresh_from_db()
    assert response.status_code == 200
    assert campaign.status == CampaignStatus.ENDED
