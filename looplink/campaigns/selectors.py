from looplink.campaigns.models import Campaign, CampaignStatus
from looplink.campaigns.transitions import is_legal_transition
from looplink.campaigns.validators import offers_present, window_is_valid_for_launch


def list_campaigns():
    return Campaign.objects.order_by("-created_at")


def get_campaign_by_token(token):
    return Campaign.objects.filter(token=token).first()


def can_schedule(campaign):
    return (
        is_legal_transition(campaign.status, CampaignStatus.SCHEDULED)
        and window_is_valid_for_launch(campaign)
        and offers_present(campaign)
    )


def can_launch(campaign):
    return (
        is_legal_transition(campaign.status, CampaignStatus.LIVE)
        and window_is_valid_for_launch(campaign)
        and offers_present(campaign)
    )


def can_end(campaign):
    return is_legal_transition(campaign.status, CampaignStatus.ENDED)


def can_edit(campaign):
    return campaign.status == CampaignStatus.DRAFT


def available_transitions(campaign):
    """
    The single source of truth for which actions the UI should currently offer.
    Services re-check these same conditions server-side before mutating, so this
    is a hint for rendering, never the sole guard.
    """
    return {
        "can_edit": can_edit(campaign),
        "can_schedule": can_schedule(campaign),
        "can_launch": can_launch(campaign),
        "can_end": can_end(campaign),
    }


def enrollment_count(campaign):
    return campaign.enrollments.count()


def recent_enrollments(campaign, limit=10):
    return campaign.enrollments.order_by("-created_at")[:limit]
