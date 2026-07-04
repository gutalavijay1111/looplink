import pytest

from looplink.campaigns import services
from looplink.campaigns.exceptions import CampaignNotEnrollableError, CampaignValidationError
from looplink.campaigns.models import CampaignStatus, Enrollment

pytestmark = pytest.mark.django_db


def test_enroll_on_live_campaign_creates_enrollment(make_campaign):
    campaign = make_campaign(status=CampaignStatus.LIVE)

    enrollment, created = services.enroll(campaign, "Shopper@Example.com")

    assert created is True
    assert enrollment.normalized_identity == "shopper@example.com"


def test_enroll_twice_with_same_identity_recognizes_not_duplicates(make_campaign):
    campaign = make_campaign(status=CampaignStatus.LIVE)

    first, first_created = services.enroll(campaign, "shopper@example.com")
    second, second_created = services.enroll(campaign, "  SHOPPER@EXAMPLE.COM  ")

    assert first_created is True
    assert second_created is False
    assert first.pk == second.pk
    assert Enrollment.objects.filter(campaign=campaign).count() == 1


def test_enroll_rejects_non_live_campaign(make_campaign):
    campaign = make_campaign(status=CampaignStatus.DRAFT)

    with pytest.raises(CampaignNotEnrollableError):
        services.enroll(campaign, "shopper@example.com")


def test_enroll_rejects_invalid_identity(make_campaign):
    campaign = make_campaign(status=CampaignStatus.LIVE)

    with pytest.raises(CampaignValidationError):
        services.enroll(campaign, "not-an-identity")


def test_same_normalized_phone_dedups_despite_formatting_differences(make_campaign):
    campaign = make_campaign(status=CampaignStatus.LIVE)

    first, first_created = services.enroll(campaign, "(555) 123-4567")
    second, second_created = services.enroll(campaign, "555-123-4567")

    assert first_created is True
    assert second_created is False
    assert first.pk == second.pk
