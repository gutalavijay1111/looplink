import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from looplink.campaigns.models import CampaignStatus

pytestmark = pytest.mark.django_db


@pytest.fixture()
def admin_client(client):
    User = get_user_model()
    user = User.objects.create_superuser(username="admin", email="admin@example.com", password="password")
    client.force_login(user)
    return client


def test_admin_change_view_does_not_offer_a_save_button(admin_client, make_campaign):
    campaign = make_campaign()

    response = admin_client.get(reverse("admin:campaigns_campaign_change", args=[campaign.pk]))

    assert response.status_code == 200
    assert b'name="_save"' not in response.content


def test_admin_cannot_change_campaign_status(admin_client, make_campaign):
    campaign = make_campaign(status=CampaignStatus.LIVE)

    response = admin_client.post(
        reverse("admin:campaigns_campaign_change", args=[campaign.pk]),
        {"name": campaign.name, "status": CampaignStatus.DRAFT},
    )

    campaign.refresh_from_db()
    assert response.status_code == 403
    assert campaign.status == CampaignStatus.LIVE


def test_admin_cannot_add_campaign(admin_client):
    response = admin_client.get(reverse("admin:campaigns_campaign_add"))

    assert response.status_code == 403


def test_admin_cannot_delete_campaign(admin_client, make_campaign):
    campaign = make_campaign()

    response = admin_client.post(reverse("admin:campaigns_campaign_delete", args=[campaign.pk]))

    assert response.status_code == 403
    assert type(campaign).objects.filter(pk=campaign.pk).exists()


def test_admin_changelist_is_still_viewable(admin_client, make_campaign):
    make_campaign(name="Visible Campaign")

    response = admin_client.get(reverse("admin:campaigns_campaign_changelist"))

    assert response.status_code == 200
    assert b"Visible Campaign" in response.content
