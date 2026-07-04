from datetime import timedelta

import pytest
from django.utils import timezone

from looplink.campaigns.exceptions import CampaignValidationError
from looplink.campaigns.models import OfferType
from looplink.campaigns.validators import validate_details, validate_offer_params


@pytest.mark.django_db()
def test_validate_details_requires_name():
    now = timezone.now()
    with pytest.raises(CampaignValidationError) as exc_info:
        validate_details(name="", starts_at=now, ends_at=now + timedelta(days=1))

    assert "name" in exc_info.value.errors


@pytest.mark.django_db()
def test_validate_details_rejects_end_before_start():
    now = timezone.now()
    with pytest.raises(CampaignValidationError) as exc_info:
        validate_details(name="Sale", starts_at=now, ends_at=now - timedelta(days=1))

    assert "ends_at" in exc_info.value.errors


@pytest.mark.django_db()
def test_validate_details_rejects_duplicate_name_case_insensitively(make_campaign):
    make_campaign(name="Summer Sale")
    now = timezone.now()

    with pytest.raises(CampaignValidationError) as exc_info:
        validate_details(name="summer sale", starts_at=now, ends_at=now + timedelta(days=1))

    assert "name" in exc_info.value.errors


@pytest.mark.django_db()
def test_validate_details_allows_campaign_to_keep_its_own_name(make_campaign):
    campaign = make_campaign(name="Summer Sale")
    now = timezone.now()

    validate_details(
        name="Summer Sale",
        starts_at=now,
        ends_at=now + timedelta(days=1),
        exclude_pk=campaign.pk,
    )


@pytest.mark.parametrize(
    ("offer_type", "params"),
    [
        (OfferType.PRODUCT_PERCENT_DISCOUNT, {"percent": 10, "applies_to": "Snacks"}),
        (OfferType.CART_FIXED_DISCOUNT, {"amount_off": 5, "min_basket": 20}),
        (OfferType.STICKER_EARN, {"stickers": 1, "per_amount": 10}),
    ],
)
def test_validate_offer_params_accepts_valid_input(offer_type, params):
    cleaned = validate_offer_params(offer_type, params)

    assert cleaned


def test_validate_offer_params_rejects_missing_percent():
    with pytest.raises(CampaignValidationError) as exc_info:
        validate_offer_params(OfferType.PRODUCT_PERCENT_DISCOUNT, {"applies_to": "Snacks"})

    assert "percent" in exc_info.value.errors


def test_validate_offer_params_rejects_percent_over_100():
    with pytest.raises(CampaignValidationError) as exc_info:
        validate_offer_params(OfferType.PRODUCT_PERCENT_DISCOUNT, {"percent": 150, "applies_to": "Snacks"})

    assert "percent" in exc_info.value.errors


def test_validate_offer_params_rejects_negative_min_basket():
    with pytest.raises(CampaignValidationError) as exc_info:
        validate_offer_params(OfferType.CART_FIXED_DISCOUNT, {"amount_off": 5, "min_basket": -1})

    assert "min_basket" in exc_info.value.errors


def test_validate_offer_params_rejects_zero_stickers():
    with pytest.raises(CampaignValidationError) as exc_info:
        validate_offer_params(OfferType.STICKER_EARN, {"stickers": 0, "per_amount": 10})

    assert "stickers" in exc_info.value.errors
