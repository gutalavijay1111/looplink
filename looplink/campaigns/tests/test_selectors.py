from datetime import timedelta

import pytest
from django.utils import timezone

from looplink.campaigns import selectors
from looplink.campaigns.models import CampaignStatus

pytestmark = pytest.mark.django_db


def test_draft_with_no_offers_cannot_schedule_or_launch(make_campaign):
    campaign = make_campaign()

    transitions = selectors.available_transitions(campaign)

    assert transitions == {"can_edit": True, "can_schedule": False, "can_launch": False, "can_end": False}


def test_draft_with_offer_and_valid_window_can_schedule_and_launch(make_campaign, make_offer):
    campaign = make_campaign()
    make_offer(campaign)

    transitions = selectors.available_transitions(campaign)

    assert transitions["can_schedule"] is True
    assert transitions["can_launch"] is True


def test_draft_with_past_window_cannot_schedule_or_launch(make_campaign, make_offer):
    now = timezone.now()
    campaign = make_campaign(starts_at=now - timedelta(days=2), ends_at=now - timedelta(days=1))
    make_offer(campaign)

    transitions = selectors.available_transitions(campaign)

    assert transitions["can_schedule"] is False
    assert transitions["can_launch"] is False


def test_scheduled_campaign_can_launch_but_not_schedule_again(make_campaign, make_offer):
    campaign = make_campaign(status=CampaignStatus.SCHEDULED)
    make_offer(campaign)

    transitions = selectors.available_transitions(campaign)

    assert transitions["can_edit"] is False
    assert transitions["can_schedule"] is False
    assert transitions["can_launch"] is True
    assert transitions["can_end"] is False


def test_live_campaign_is_enrollable_and_can_end(make_campaign):
    campaign = make_campaign(status=CampaignStatus.LIVE)

    assert selectors.is_enrollable(campaign) is True
    assert selectors.available_transitions(campaign)["can_end"] is True


def test_ended_campaign_has_no_legal_transitions(make_campaign):
    campaign = make_campaign(status=CampaignStatus.ENDED)

    transitions = selectors.available_transitions(campaign)

    assert not any(transitions.values())
    assert selectors.is_enrollable(campaign) is False


def test_get_campaign_by_token_returns_none_for_unknown_token():
    assert selectors.get_campaign_by_token("does-not-exist") is None


def test_get_campaign_by_token_finds_match(make_campaign):
    campaign = make_campaign()

    assert selectors.get_campaign_by_token(campaign.token) == campaign
