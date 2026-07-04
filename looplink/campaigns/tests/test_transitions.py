from looplink.campaigns.models import CampaignStatus
from looplink.campaigns.transitions import is_legal_transition, legal_sources_for


def test_draft_can_reach_scheduled_or_live():
    assert is_legal_transition(CampaignStatus.DRAFT, CampaignStatus.SCHEDULED) is True
    assert is_legal_transition(CampaignStatus.DRAFT, CampaignStatus.LIVE) is True
    assert is_legal_transition(CampaignStatus.DRAFT, CampaignStatus.ENDED) is False


def test_scheduled_can_only_reach_live():
    assert is_legal_transition(CampaignStatus.SCHEDULED, CampaignStatus.LIVE) is True
    assert is_legal_transition(CampaignStatus.SCHEDULED, CampaignStatus.DRAFT) is False
    assert is_legal_transition(CampaignStatus.SCHEDULED, CampaignStatus.SCHEDULED) is False


def test_live_can_only_reach_ended():
    assert is_legal_transition(CampaignStatus.LIVE, CampaignStatus.ENDED) is True
    assert is_legal_transition(CampaignStatus.LIVE, CampaignStatus.DRAFT) is False


def test_ended_is_terminal():
    assert is_legal_transition(CampaignStatus.ENDED, CampaignStatus.LIVE) is False
    assert is_legal_transition(CampaignStatus.ENDED, CampaignStatus.DRAFT) is False
    assert is_legal_transition(CampaignStatus.ENDED, CampaignStatus.SCHEDULED) is False


def test_legal_sources_for_live_includes_draft_and_scheduled():
    assert legal_sources_for(CampaignStatus.LIVE) == {CampaignStatus.DRAFT, CampaignStatus.SCHEDULED}


def test_legal_sources_for_scheduled_is_draft_only():
    assert legal_sources_for(CampaignStatus.SCHEDULED) == {CampaignStatus.DRAFT}


def test_legal_sources_for_ended_is_live_only():
    assert legal_sources_for(CampaignStatus.ENDED) == {CampaignStatus.LIVE}


def test_legal_sources_for_draft_is_empty():
    assert legal_sources_for(CampaignStatus.DRAFT) == set()
