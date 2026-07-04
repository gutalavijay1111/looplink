import pytest
from django.core.cache import cache

from looplink.campaigns import activity_cache
from looplink.campaigns.models import CampaignStatus, Enrollment, IdentityType

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _enroll(campaign, identity):
    return Enrollment.objects.create(
        campaign=campaign,
        raw_identity=identity,
        normalized_identity=identity,
        identity_type=IdentityType.EMAIL,
    )


def test_get_enrollment_count_populates_cache_from_db_on_miss(make_campaign):
    campaign = make_campaign(status=CampaignStatus.LIVE)
    _enroll(campaign, "a@example.com")
    _enroll(campaign, "b@example.com")

    assert cache.get(activity_cache._count_key(campaign.pk)) is None
    count = activity_cache.get_enrollment_count(campaign)

    assert count == 2
    assert cache.get(activity_cache._count_key(campaign.pk)) == 2


def test_get_enrollment_count_serves_from_cache_without_querying_db(make_campaign):
    campaign = make_campaign(status=CampaignStatus.LIVE)
    _enroll(campaign, "a@example.com")
    cache.set(activity_cache._count_key(campaign.pk), 999)  # deliberately wrong, proves cache wins

    assert activity_cache.get_enrollment_count(campaign) == 999


def test_get_recent_enrollments_populates_cache_from_db_on_miss(make_campaign):
    campaign = make_campaign(status=CampaignStatus.LIVE)
    _enroll(campaign, "a@example.com")

    recent = activity_cache.get_recent_enrollments(campaign)

    assert len(recent) == 1
    assert recent[0]["identity"] == "a@example.com"
    assert cache.get(activity_cache._recent_key(campaign.pk)) == recent


def test_record_enrollment_increments_warm_cache(make_campaign):
    campaign = make_campaign(status=CampaignStatus.LIVE)
    activity_cache.get_enrollment_count(campaign)  # warm the cache at 0

    enrollment = _enroll(campaign, "a@example.com")
    activity_cache.record_enrollment(campaign, enrollment)

    assert cache.get(activity_cache._count_key(campaign.pk)) == 1


def test_record_enrollment_primes_cold_cache_from_db(make_campaign):
    campaign = make_campaign(status=CampaignStatus.LIVE)
    enrollment = _enroll(campaign, "a@example.com")

    activity_cache.record_enrollment(campaign, enrollment)

    assert cache.get(activity_cache._count_key(campaign.pk)) == 1


def test_record_enrollment_prepends_to_recent_list(make_campaign):
    campaign = make_campaign(status=CampaignStatus.LIVE)
    first = _enroll(campaign, "first@example.com")
    activity_cache.record_enrollment(campaign, first)

    second = _enroll(campaign, "second@example.com")
    activity_cache.record_enrollment(campaign, second)

    recent = cache.get(activity_cache._recent_key(campaign.pk))
    assert [r["identity"] for r in recent] == ["second@example.com", "first@example.com"]


def test_record_enrollment_trims_recent_list_to_limit(make_campaign):
    campaign = make_campaign(status=CampaignStatus.LIVE)
    for i in range(activity_cache.RECENT_LIMIT + 3):
        enrollment = _enroll(campaign, f"shopper{i}@example.com")
        activity_cache.record_enrollment(campaign, enrollment)

    recent = cache.get(activity_cache._recent_key(campaign.pk))
    assert len(recent) == activity_cache.RECENT_LIMIT
