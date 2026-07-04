from datetime import timedelta

import pytest
from django.utils import timezone

from looplink.campaigns.models import Campaign, Offer, OfferType


@pytest.fixture()
def make_campaign(db):
    def _make_campaign(**kwargs):
        now = timezone.now()
        defaults = {
            "name": "Summer Sale",
            "description": "Seasonal offers",
            "starts_at": now,
            "ends_at": now + timedelta(days=7),
        }
        defaults.update(kwargs)
        return Campaign.objects.create(**defaults)

    return _make_campaign


@pytest.fixture()
def make_offer():
    def _make_offer(campaign, **kwargs):
        defaults = {
            "offer_type": OfferType.PRODUCT_PERCENT_DISCOUNT,
            "params": {"percent": 10, "applies_to": "Snacks"},
        }
        defaults.update(kwargs)
        return Offer.objects.create(campaign=campaign, **defaults)

    return _make_offer
