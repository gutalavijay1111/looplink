from datetime import timedelta

import pytest
from django.utils import timezone

from looplink.campaigns.forms import (
    CampaignDetailsForm,
    CartFixedDiscountOfferForm,
    EnrollForm,
    PercentDiscountOfferForm,
    StickerEarnOfferForm,
)

pytestmark = pytest.mark.django_db


def _details_data(**overrides):
    now = timezone.now().replace(microsecond=0)
    data = {
        "name": "New name",
        "description": "",
        "starts_at": now.strftime("%Y-%m-%dT%H:%M"),
        "ends_at": (now + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M"),
    }
    data.update(overrides)
    return data


def test_details_form_requires_name(make_campaign):
    campaign = make_campaign()

    form = CampaignDetailsForm(_details_data(name=""), instance=campaign)

    assert not form.is_valid()
    assert "Name is required." in form.errors["name"]


def test_details_form_rejects_end_before_start(make_campaign):
    campaign = make_campaign()
    now = timezone.now().replace(microsecond=0)

    form = CampaignDetailsForm(
        _details_data(
            starts_at=now.strftime("%Y-%m-%dT%H:%M"), ends_at=(now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        ),
        instance=campaign,
    )

    assert not form.is_valid()
    assert "End must be after start." in form.errors["ends_at"]


def test_details_form_rejects_duplicate_name_case_insensitively(make_campaign):
    make_campaign(name="Summer Sale")
    campaign = make_campaign(name="Winter Sale")

    form = CampaignDetailsForm(_details_data(name="summer sale"), instance=campaign)

    assert not form.is_valid()
    assert "A campaign with this name already exists." in form.errors["name"]


def test_details_form_allows_campaign_to_keep_its_own_name(make_campaign):
    campaign = make_campaign(name="Summer Sale")

    form = CampaignDetailsForm(_details_data(name="Summer Sale"), instance=campaign)

    assert form.is_valid(), form.errors


def test_percent_offer_form_rejects_missing_percent():
    form = PercentDiscountOfferForm({"applies_to": "Snacks"})

    assert not form.is_valid()
    assert "percent" in form.errors


def test_percent_offer_form_rejects_percent_over_100():
    form = PercentDiscountOfferForm({"percent": "150", "applies_to": "Snacks"})

    assert not form.is_valid()
    assert "Must be at most 100." in form.errors["percent"]


def test_percent_offer_form_accepts_valid_input():
    form = PercentDiscountOfferForm({"percent": "10", "applies_to": "Snacks"})

    assert form.is_valid(), form.errors
    assert form.cleaned_data == {"percent": 10.0, "applies_to": "Snacks"}


def test_cart_offer_form_rejects_negative_min_basket():
    form = CartFixedDiscountOfferForm({"amount_off": "5", "min_basket": "-1"})

    assert not form.is_valid()
    assert "Must be 0 or greater." in form.errors["min_basket"]


def test_sticker_offer_form_rejects_zero_stickers():
    form = StickerEarnOfferForm({"stickers": "0", "per_amount": "10"})

    assert not form.is_valid()
    assert "Must be greater than 0." in form.errors["stickers"]


def test_enroll_form_rejects_invalid_identity():
    form = EnrollForm({"identity": "not-an-identity"})

    assert not form.is_valid()
    assert "Enter a valid phone number or email address." in form.errors["identity"]


def test_enroll_form_accepts_email():
    form = EnrollForm({"identity": "shopper@example.com"})

    assert form.is_valid(), form.errors
