from datetime import timedelta

import pytest
from django.utils import timezone

from looplink.campaigns import services
from looplink.campaigns.exceptions import (
    CampaignValidationError,
    IllegalTransitionError,
    StaleCampaignError,
)
from looplink.campaigns.models import CampaignStatus

pytestmark = pytest.mark.django_db


def test_launch_requires_at_least_one_offer(make_campaign):
    campaign = make_campaign()

    with pytest.raises(CampaignValidationError) as exc_info:
        services.launch(campaign, expected_updated_at=campaign.updated_at)

    assert "offers" in exc_info.value.errors
    campaign.refresh_from_db()
    assert campaign.status == CampaignStatus.DRAFT


def test_launch_requires_a_window_not_in_the_past(make_campaign, make_offer):
    now = timezone.now()
    campaign = make_campaign(starts_at=now - timedelta(days=2), ends_at=now - timedelta(days=1))
    make_offer(campaign)

    with pytest.raises(CampaignValidationError) as exc_info:
        services.launch(campaign, expected_updated_at=campaign.updated_at)

    assert "ends_at" in exc_info.value.errors


def test_launch_from_draft_succeeds_with_offer_and_valid_window(make_campaign, make_offer):
    campaign = make_campaign()
    make_offer(campaign)

    result = services.launch(campaign, expected_updated_at=campaign.updated_at)

    assert result.status == CampaignStatus.LIVE


def test_launch_from_scheduled_succeeds(make_campaign, make_offer):
    campaign = make_campaign(status=CampaignStatus.SCHEDULED)
    make_offer(campaign)

    result = services.launch(campaign, expected_updated_at=campaign.updated_at)

    assert result.status == CampaignStatus.LIVE


def test_launch_from_live_is_illegal(make_campaign, make_offer):
    campaign = make_campaign(status=CampaignStatus.LIVE)
    make_offer(campaign)

    with pytest.raises(IllegalTransitionError):
        services.launch(campaign, expected_updated_at=campaign.updated_at)


def test_launch_from_ended_is_illegal(make_campaign, make_offer):
    campaign = make_campaign(status=CampaignStatus.ENDED)
    make_offer(campaign)

    with pytest.raises(IllegalTransitionError):
        services.launch(campaign, expected_updated_at=campaign.updated_at)


def test_schedule_requires_offer_and_valid_window(make_campaign):
    campaign = make_campaign()

    with pytest.raises(CampaignValidationError):
        services.schedule(campaign, expected_updated_at=campaign.updated_at)


def test_schedule_from_draft_succeeds(make_campaign, make_offer):
    campaign = make_campaign()
    make_offer(campaign)

    result = services.schedule(campaign, expected_updated_at=campaign.updated_at)

    assert result.status == CampaignStatus.SCHEDULED


def test_schedule_from_scheduled_is_illegal(make_campaign, make_offer):
    campaign = make_campaign(status=CampaignStatus.SCHEDULED)
    make_offer(campaign)

    with pytest.raises(IllegalTransitionError):
        services.schedule(campaign, expected_updated_at=campaign.updated_at)


def test_end_from_live_succeeds(make_campaign):
    campaign = make_campaign(status=CampaignStatus.LIVE)

    result = services.end(campaign, expected_updated_at=campaign.updated_at)

    assert result.status == CampaignStatus.ENDED


def test_end_from_draft_is_illegal(make_campaign):
    campaign = make_campaign()

    with pytest.raises(IllegalTransitionError):
        services.end(campaign, expected_updated_at=campaign.updated_at)


def test_end_from_scheduled_is_illegal(make_campaign, make_offer):
    campaign = make_campaign(status=CampaignStatus.SCHEDULED)
    make_offer(campaign)

    with pytest.raises(IllegalTransitionError):
        services.end(campaign, expected_updated_at=campaign.updated_at)


def test_end_is_forward_only_and_terminal(make_campaign):
    campaign = make_campaign(status=CampaignStatus.ENDED)

    with pytest.raises(IllegalTransitionError):
        services.end(campaign, expected_updated_at=campaign.updated_at)


def test_launch_with_stale_expected_updated_at_is_rejected(make_campaign, make_offer):
    """
    Simulates: user A opens a draft; user B launches it; user A's (now stale)
    view attempts a transition using the updated_at it originally loaded.
    """
    campaign = make_campaign()
    make_offer(campaign)
    stale_updated_at = campaign.updated_at

    services.launch(campaign, expected_updated_at=stale_updated_at)
    campaign.refresh_from_db()
    services.end(campaign, expected_updated_at=campaign.updated_at)

    with pytest.raises(StaleCampaignError):
        services.launch(campaign, expected_updated_at=stale_updated_at)
