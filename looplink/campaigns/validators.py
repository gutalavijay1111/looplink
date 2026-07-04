from django.utils import timezone

from looplink.campaigns.exceptions import CampaignValidationError
from looplink.campaigns.models import Campaign, OfferType


def validate_details(*, name, starts_at, ends_at, exclude_pk=None):
    """Basic sanity checks that apply whenever a draft is saved."""
    errors = {}
    stripped_name = (name or "").strip()
    if not stripped_name:
        errors["name"] = ["Name is required."]
    else:
        conflicts = Campaign.objects.filter(name__iexact=stripped_name)
        if exclude_pk is not None:
            conflicts = conflicts.exclude(pk=exclude_pk)
        if conflicts.exists():
            errors["name"] = ["A campaign with this name already exists."]
    if not starts_at:
        errors["starts_at"] = ["Start date is required."]
    if not ends_at:
        errors["ends_at"] = ["End date is required."]
    if starts_at and ends_at and ends_at <= starts_at:
        errors.setdefault("ends_at", []).append("End must be after start.")
    if errors:
        raise CampaignValidationError(errors)


def window_is_valid_for_launch(campaign):
    return campaign.ends_at > timezone.now() and campaign.ends_at > campaign.starts_at


def offers_present(campaign):
    return campaign.offers.exists()


def validate_launch_readiness(campaign):
    """Raises with field-level detail; used where a human-readable reason is needed."""
    errors = {}
    if not campaign.ends_at > campaign.starts_at:
        errors["ends_at"] = ["End must be after start."]
    elif campaign.ends_at <= timezone.now():
        errors["ends_at"] = ["End date must be in the future to launch."]
    if not offers_present(campaign):
        errors["offers"] = ["Add at least one offer before launching."]
    if errors:
        raise CampaignValidationError(errors)


def _positive_number(value, field, *, max_value=None):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise CampaignValidationError({field: ["Enter a number."]}) from None
    if number <= 0:
        raise CampaignValidationError({field: ["Must be greater than 0."]})
    if max_value is not None and number > max_value:
        raise CampaignValidationError({field: [f"Must be at most {max_value}."]})
    return number


def _non_negative_number(value, field):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise CampaignValidationError({field: ["Enter a number."]}) from None
    if number < 0:
        raise CampaignValidationError({field: ["Must be 0 or greater."]})
    return number


def _positive_int(value, field):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise CampaignValidationError({field: ["Enter a whole number."]}) from None
    if number <= 0:
        raise CampaignValidationError({field: ["Must be greater than 0."]})
    return number


def _non_empty_str(value, field):
    text = (value or "").strip()
    if not text:
        raise CampaignValidationError({field: ["This field is required."]})
    return text


def validate_offer_params(offer_type, params):
    """Validates and returns a cleaned params dict for the given offer type."""
    params = params or {}
    if offer_type == OfferType.PRODUCT_PERCENT_DISCOUNT:
        return {
            "percent": _positive_number(params.get("percent"), "percent", max_value=100),
            "applies_to": _non_empty_str(params.get("applies_to"), "applies_to"),
        }
    if offer_type == OfferType.CART_FIXED_DISCOUNT:
        return {
            "amount_off": _positive_number(params.get("amount_off"), "amount_off"),
            "min_basket": _non_negative_number(params.get("min_basket"), "min_basket"),
        }
    if offer_type == OfferType.STICKER_EARN:
        return {
            "stickers": _positive_int(params.get("stickers"), "stickers"),
            "per_amount": _positive_number(params.get("per_amount"), "per_amount"),
        }
    raise CampaignValidationError({"offer_type": [f"Unknown offer type: {offer_type}"]})
