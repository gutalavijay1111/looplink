import pytest
from django.db import IntegrityError

from looplink.campaigns.models import CampaignStatus, Enrollment, IdentityType

pytestmark = pytest.mark.django_db


def test_campaign_defaults_to_draft(make_campaign):
    campaign = make_campaign()

    assert campaign.status == CampaignStatus.DRAFT


def test_campaign_token_is_generated_and_unique(make_campaign):
    first = make_campaign()
    second = make_campaign()

    assert first.token
    assert first.token != second.token


def test_campaign_name_must_be_unique_case_insensitively(make_campaign):
    make_campaign(name="Summer Sale")

    with pytest.raises(IntegrityError):
        make_campaign(name="summer sale")


def test_offer_belongs_to_campaign_with_params(make_campaign, make_offer):
    campaign = make_campaign()

    offer = make_offer(campaign, params={"percent": 10, "applies_to": "All snacks"})

    assert offer in campaign.offers.all()
    assert offer.params["percent"] == 10


def test_enrollment_dedups_same_identity_on_same_campaign(make_campaign):
    campaign = make_campaign()
    Enrollment.objects.create(
        campaign=campaign,
        raw_identity="Shopper@Example.com",
        normalized_identity="shopper@example.com",
        identity_type=IdentityType.EMAIL,
    )

    with pytest.raises(IntegrityError):
        Enrollment.objects.create(
            campaign=campaign,
            raw_identity="shopper@example.com",
            normalized_identity="shopper@example.com",
            identity_type=IdentityType.EMAIL,
        )


def test_same_identity_can_enroll_in_different_campaigns(make_campaign):
    first_campaign = make_campaign(name="Campaign A")
    second_campaign = make_campaign(name="Campaign B")

    Enrollment.objects.create(
        campaign=first_campaign,
        raw_identity="shopper@example.com",
        normalized_identity="shopper@example.com",
        identity_type=IdentityType.EMAIL,
    )
    Enrollment.objects.create(
        campaign=second_campaign,
        raw_identity="shopper@example.com",
        normalized_identity="shopper@example.com",
        identity_type=IdentityType.EMAIL,
    )

    assert Enrollment.objects.count() == 2
