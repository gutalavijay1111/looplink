from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from looplink.campaigns.models import Campaign, Offer, OfferType

pytestmark = pytest.mark.django_db


def make_campaign(**kwargs):
    now = timezone.now()
    defaults = {
        "name": "Summer Sale",
        "description": "Seasonal offers",
        "starts_at": now,
        "ends_at": now + timedelta(days=7),
    }
    defaults.update(kwargs)
    return Campaign.objects.create(**defaults)


def test_list_view_shows_empty_state_with_no_campaigns(client):
    response = client.get(reverse("builder_campaign_list"))

    assert response.status_code == 200
    assert "No campaigns yet" in response.content.decode()


def test_list_view_shows_campaign_name_and_status(client):
    make_campaign(name="Summer Sale")

    response = client.get(reverse("builder_campaign_list"))

    content = response.content.decode()
    assert "Summer Sale" in content
    assert "Draft" in content


def test_detail_view_shows_offer_and_params(client):
    campaign = make_campaign()
    Offer.objects.create(
        campaign=campaign,
        offer_type=OfferType.PRODUCT_PERCENT_DISCOUNT,
        params={"percent": 15, "applies_to": "Snacks"},
    )

    response = client.get(reverse("builder_campaign_detail", args=[campaign.pk]))

    content = response.content.decode()
    assert response.status_code == 200
    assert "Product percent discount" in content
    assert "Snacks" in content


def test_detail_view_404s_for_unknown_campaign(client):
    response = client.get(reverse("builder_campaign_detail", args=[999]))

    assert response.status_code == 404
