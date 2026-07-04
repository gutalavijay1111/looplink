from looplink.campaigns.models import Campaign, CampaignStatus, Enrollment
from looplink.campaigns.validators import offers_present, window_is_valid_for_launch


def list_campaigns():
    return Campaign.objects.order_by("-created_at")


def get_campaign(pk):
    return Campaign.objects.get(pk=pk)


def get_campaign_by_token(token):
    return Campaign.objects.filter(token=token).first()


def is_enrollable(campaign):
    return campaign.status == CampaignStatus.LIVE


def can_schedule(campaign):
    return campaign.status == CampaignStatus.DRAFT and window_is_valid_for_launch(campaign) and offers_present(campaign)


def can_launch(campaign):
    return (
        campaign.status in (CampaignStatus.DRAFT, CampaignStatus.SCHEDULED)
        and window_is_valid_for_launch(campaign)
        and offers_present(campaign)
    )


def can_end(campaign):
    return campaign.status == CampaignStatus.LIVE


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


def find_enrollment(campaign, normalized_identity):
    return Enrollment.objects.filter(campaign=campaign, normalized_identity=normalized_identity).first()


def enrollment_count(campaign):
    return campaign.enrollments.count()
