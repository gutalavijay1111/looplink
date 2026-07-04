from datetime import timedelta

import pytest
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from looplink.campaigns import services
from looplink.campaigns.models import Campaign, CampaignStatus

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


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


def test_shopper_enrollment_appears_in_builder_live_activity(client):
    campaign = make_campaign(status=CampaignStatus.LIVE)
    detail_url = reverse("builder_campaign_detail", args=[campaign.pk])

    # Warm the cache before the enrollment, the way an open builder tab would.
    client.get(detail_url, HTTP_DJ_HX_ACTION="activity")

    services.enroll(campaign, "shopper@example.com")

    response = client.get(detail_url, HTTP_DJ_HX_ACTION="activity")
    content = response.content.decode()
    assert "shopper@example.com" in content
    assert "1 enrolled" in content


def test_repeat_enrollment_does_not_double_count_in_live_activity(client):
    campaign = make_campaign(status=CampaignStatus.LIVE)
    detail_url = reverse("builder_campaign_detail", args=[campaign.pk])

    services.enroll(campaign, "shopper@example.com")
    services.enroll(campaign, "shopper@example.com")

    response = client.get(detail_url, HTTP_DJ_HX_ACTION="activity")
    assert "1 enrolled" in response.content.decode()
