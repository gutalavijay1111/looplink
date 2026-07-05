from django.utils import timezone

from looplink.campaigns.exceptions import CampaignValidationError


def window_is_valid_for_launch(campaign):
    return campaign.ends_at > timezone.now() and campaign.ends_at > campaign.starts_at


def offers_present(campaign):
    return campaign.offers.exists()


def validate_launch_readiness(campaign):
    """
    Checks campaign state, not user input — schedule/launch are button clicks with
    no form, so there's nothing for a Django Form to validate here.
    """
    errors = {}
    if not campaign.ends_at > campaign.starts_at:
        errors["ends_at"] = ["End must be after start."]
    elif campaign.ends_at <= timezone.now():
        errors["ends_at"] = ["End date must be in the future to launch."]
    if not offers_present(campaign):
        errors["offers"] = ["Add at least one offer before launching."]
    if errors:
        raise CampaignValidationError(errors)
