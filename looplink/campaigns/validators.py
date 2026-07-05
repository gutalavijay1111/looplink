from django.core.exceptions import ValidationError
from django.utils import timezone

from looplink.campaigns.exceptions import CampaignValidationError
from looplink.campaigns.models import NAME_ALREADY_EXISTS_MSG, Campaign

PERCENT_MAX = 100
REQUIRED_MSG = "This field is required."
POSITIVE_MSG = "Must be greater than 0."
NON_NEGATIVE_MSG = "Must be 0 or greater."
END_AFTER_START_MSG = "End must be after start."


def max_value_msg(max_value):
    return f"Must be at most {max_value}."


def validate_positive(value, *, max_value=None):
    """
    The one place "is this number acceptable" is decided for offer amounts.
    Called from a Form's clean_<field>() (the server-authoritative check); the
    widget's min/max attrs are set from these same bounds so the browser also
    rejects an out-of-range value before it's ever submitted — one set of
    numbers driving both, rather than a second copy of "0.01" or "100" living
    in the widget markup.
    """
    if value is None or value <= 0:
        raise ValidationError(POSITIVE_MSG)
    if max_value is not None and value > max_value:
        raise ValidationError(max_value_msg(max_value))
    return value


def validate_non_negative(value):
    if value is None or value < 0:
        raise ValidationError(NON_NEGATIVE_MSG)
    return value


def validate_name_unique(name, *, exclude_pk=None):
    """
    The model's UniqueConstraint(Lower("name")) is the authoritative backstop
    (checked again on save); this pre-check exists purely so the error attaches
    to the "name" field instead of Django's form-wide "__all__" bucket.
    """
    conflicts = Campaign.objects.filter(name__iexact=name)
    if exclude_pk is not None:
        conflicts = conflicts.exclude(pk=exclude_pk)
    if conflicts.exists():
        raise ValidationError(NAME_ALREADY_EXISTS_MSG)
    return name


def window_is_valid_for_launch(campaign):
    return campaign.ends_at > timezone.now() and campaign.ends_at > campaign.starts_at


def offers_present(campaign):
    return campaign.offers.exists()


def validate_launch_readiness(campaign):
    """
    Checks campaign state, not user input — schedule/launch are button clicks
    with no form, so there's nothing for a Django Form to validate here.
    """
    errors = {}
    if not campaign.ends_at > campaign.starts_at:
        errors["ends_at"] = [END_AFTER_START_MSG]
    elif campaign.ends_at <= timezone.now():
        errors["ends_at"] = ["End date must be in the future to launch."]
    if not offers_present(campaign):
        errors["offers"] = ["Add at least one offer before launching."]
    if errors:
        raise CampaignValidationError(errors)
