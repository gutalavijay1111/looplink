from datetime import timedelta

import pytest
from django.utils import timezone

from looplink.campaigns import services
from looplink.campaigns.exceptions import (
    CampaignLockedError,
    CampaignValidationError,
    StaleCampaignError,
)
from looplink.campaigns.models import CampaignStatus, Offer, OfferType

pytestmark = pytest.mark.django_db


def test_create_draft_generates_unique_names_back_to_back():
    first = services.create_draft()
    second = services.create_draft()

    assert first.name != second.name


def test_update_details_on_draft_succeeds(make_campaign):
    campaign = make_campaign()
    now = timezone.now()

    updated = services.update_details(
        campaign,
        expected_updated_at=campaign.updated_at,
        name="New name",
        description="New description",
        starts_at=now,
        ends_at=now + timedelta(days=3),
    )

    assert updated.name == "New name"


def test_update_details_rejects_invalid_window(make_campaign):
    campaign = make_campaign()
    now = timezone.now()

    with pytest.raises(CampaignValidationError):
        services.update_details(
            campaign,
            expected_updated_at=campaign.updated_at,
            name="New name",
            description="",
            starts_at=now,
            ends_at=now - timedelta(days=1),
        )


def test_update_details_rejects_name_already_used_by_another_campaign(make_campaign):
    make_campaign(name="Summer Sale")
    campaign = make_campaign(name="Winter Sale")
    now = timezone.now()

    with pytest.raises(CampaignValidationError) as exc_info:
        services.update_details(
            campaign,
            expected_updated_at=campaign.updated_at,
            name="summer sale",
            description="",
            starts_at=now,
            ends_at=now + timedelta(days=3),
        )
    assert "name" in exc_info.value.errors


def test_update_details_allows_keeping_its_own_current_name(make_campaign):
    campaign = make_campaign(name="Summer Sale")
    now = timezone.now()

    updated = services.update_details(
        campaign,
        expected_updated_at=campaign.updated_at,
        name="Summer Sale",
        description="Updated description",
        starts_at=now,
        ends_at=now + timedelta(days=3),
    )

    assert updated.description == "Updated description"


def test_update_details_on_non_draft_is_locked(make_campaign):
    campaign = make_campaign(status=CampaignStatus.LIVE)
    now = timezone.now()

    with pytest.raises(CampaignLockedError):
        services.update_details(
            campaign,
            expected_updated_at=campaign.updated_at,
            name="New name",
            description="",
            starts_at=now,
            ends_at=now + timedelta(days=3),
        )


def test_update_details_with_stale_expected_updated_at_is_rejected(make_campaign):
    """User A and user B both open the same draft; B saves first, then A saves using stale data."""
    campaign = make_campaign()
    stale_updated_at = campaign.updated_at
    now = timezone.now()

    services.update_details(
        campaign,
        expected_updated_at=stale_updated_at,
        name="B's edit",
        description="",
        starts_at=now,
        ends_at=now + timedelta(days=3),
    )

    with pytest.raises(StaleCampaignError):
        services.update_details(
            campaign,
            expected_updated_at=stale_updated_at,
            name="A's edit",
            description="",
            starts_at=now,
            ends_at=now + timedelta(days=3),
        )


def test_add_offer_on_draft_succeeds(make_campaign):
    campaign = make_campaign()

    offer = services.add_offer(
        campaign,
        expected_updated_at=campaign.updated_at,
        offer_type=OfferType.STICKER_EARN,
        params={"stickers": 1, "per_amount": 10},
    )

    assert offer.campaign_id == campaign.pk
    assert offer.params == {"stickers": 1, "per_amount": 10}


def test_add_offer_rejects_invalid_params(make_campaign):
    campaign = make_campaign()

    with pytest.raises(CampaignValidationError):
        services.add_offer(
            campaign,
            expected_updated_at=campaign.updated_at,
            offer_type=OfferType.STICKER_EARN,
            params={"stickers": 0, "per_amount": 10},
        )
    assert Offer.objects.count() == 0


def test_add_offer_on_non_draft_is_locked(make_campaign):
    campaign = make_campaign(status=CampaignStatus.SCHEDULED)

    with pytest.raises(CampaignLockedError):
        services.add_offer(
            campaign,
            expected_updated_at=campaign.updated_at,
            offer_type=OfferType.STICKER_EARN,
            params={"stickers": 1, "per_amount": 10},
        )


def test_remove_offer_on_draft_succeeds(make_campaign, make_offer):
    campaign = make_campaign()
    offer = make_offer(campaign)

    services.remove_offer(campaign, expected_updated_at=campaign.updated_at, offer_id=offer.pk)

    assert not Offer.objects.filter(pk=offer.pk).exists()


def test_remove_offer_on_non_draft_is_locked(make_campaign, make_offer):
    campaign = make_campaign(status=CampaignStatus.LIVE)
    offer = make_offer(campaign)

    with pytest.raises(CampaignLockedError):
        services.remove_offer(campaign, expected_updated_at=campaign.updated_at, offer_id=offer.pk)
    assert Offer.objects.filter(pk=offer.pk).exists()
