from datetime import timedelta

import pytest
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

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


def htmx_get(client, url, action):
    return client.get(url, HTTP_DJ_HX_ACTION=action)


def test_live_campaign_page_load_shows_view_live_button_not_polling(client):
    campaign = make_campaign(status=CampaignStatus.LIVE)

    response = client.get(reverse("builder_campaign_detail", args=[campaign.pk]))

    content = response.content.decode()
    assert "View live" in content
    assert "every 5s" not in content


def test_non_live_campaign_has_no_live_activity_section(client):
    campaign = make_campaign(status=CampaignStatus.DRAFT)

    response = client.get(reverse("builder_campaign_detail", args=[campaign.pk]))

    assert "Live activity" not in response.content.decode()


def test_activity_action_starts_polling(client):
    campaign = make_campaign(status=CampaignStatus.LIVE)
    url = reverse("builder_campaign_detail", args=[campaign.pk])

    response = htmx_get(client, url, "activity")

    content = response.content.decode()
    assert "every 5s" in content
    assert "Stop" in content


def test_activity_stop_action_returns_to_paused_state(client):
    campaign = make_campaign(status=CampaignStatus.LIVE)
    url = reverse("builder_campaign_detail", args=[campaign.pk])

    response = htmx_get(client, url, "activity_stop")

    content = response.content.decode()
    assert "every 5s" not in content
    assert "View live" in content


def test_activity_action_on_ended_campaign_reports_no_longer_live(client):
    campaign = make_campaign(status=CampaignStatus.ENDED)
    url = reverse("builder_campaign_detail", args=[campaign.pk])

    response = htmx_get(client, url, "activity")

    content = response.content.decode()
    assert "no longer live" in content
    assert "every 5s" not in content
