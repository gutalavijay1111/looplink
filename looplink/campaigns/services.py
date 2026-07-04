from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from looplink.campaigns.exceptions import (
    CampaignLockedError,
    CampaignNotEnrollableError,
    IllegalTransitionError,
    StaleCampaignError,
)
from looplink.campaigns.identity import normalize_identity
from looplink.campaigns.models import Campaign, CampaignStatus, Enrollment, Offer
from looplink.campaigns.transitions import legal_sources_for
from looplink.campaigns.validators import (
    validate_details,
    validate_launch_readiness,
    validate_offer_params,
)

DEFAULT_WINDOW = timedelta(days=7)


def create_draft():
    now = timezone.now()
    return Campaign.objects.create(
        name="Untitled campaign",
        description="",
        starts_at=now,
        ends_at=now + DEFAULT_WINDOW,
    )


def _diagnose_write_failure(pk, expected_updated_at, *, required_status=None):
    """
    Called only after a conditional UPDATE affected 0 rows, to produce a specific
    error message. The UPDATE's WHERE clause is the actual correctness guard (it's
    atomic); this re-read is purely to explain *why* it failed, so there's no
    TOCTOU window that correctness depends on.
    """
    current = Campaign.objects.get(pk=pk)
    if required_status is not None and current.status != required_status:
        raise CampaignLockedError("This campaign can no longer be edited.")
    if current.updated_at != expected_updated_at:
        raise StaleCampaignError("This campaign changed since you loaded it. Refresh and try again.")
    raise IllegalTransitionError("This action is not allowed from the campaign's current status.")


@transaction.atomic
def update_details(campaign, *, expected_updated_at, name, description, starts_at, ends_at):
    validate_details(name=name, starts_at=starts_at, ends_at=ends_at)
    now = timezone.now()
    updated = Campaign.objects.filter(
        pk=campaign.pk,
        updated_at=expected_updated_at,
        status=CampaignStatus.DRAFT,
    ).update(name=name, description=description, starts_at=starts_at, ends_at=ends_at, updated_at=now)
    if not updated:
        _diagnose_write_failure(campaign.pk, expected_updated_at, required_status=CampaignStatus.DRAFT)
    campaign.refresh_from_db()
    return campaign


def _claim_version_for_draft_edit(campaign, expected_updated_at):
    """Atomically bumps updated_at iff still a draft at the expected version; returns the new timestamp."""
    now = timezone.now()
    updated = Campaign.objects.filter(
        pk=campaign.pk,
        updated_at=expected_updated_at,
        status=CampaignStatus.DRAFT,
    ).update(updated_at=now)
    if not updated:
        _diagnose_write_failure(campaign.pk, expected_updated_at, required_status=CampaignStatus.DRAFT)
    return now


@transaction.atomic
def add_offer(campaign, *, expected_updated_at, offer_type, params):
    cleaned_params = validate_offer_params(offer_type, params)
    new_updated_at = _claim_version_for_draft_edit(campaign, expected_updated_at)
    offer = Offer.objects.create(campaign=campaign, offer_type=offer_type, params=cleaned_params)
    campaign.updated_at = new_updated_at
    return offer


@transaction.atomic
def remove_offer(campaign, *, expected_updated_at, offer_id):
    new_updated_at = _claim_version_for_draft_edit(campaign, expected_updated_at)
    Offer.objects.filter(pk=offer_id, campaign=campaign).delete()
    campaign.updated_at = new_updated_at


@transaction.atomic
def schedule(campaign, *, expected_updated_at):
    validate_launch_readiness(campaign)
    now = timezone.now()
    updated = Campaign.objects.filter(
        pk=campaign.pk,
        updated_at=expected_updated_at,
        status__in=legal_sources_for(CampaignStatus.SCHEDULED),
    ).update(status=CampaignStatus.SCHEDULED, updated_at=now)
    if not updated:
        _diagnose_write_failure(campaign.pk, expected_updated_at)
    campaign.refresh_from_db()
    return campaign


@transaction.atomic
def launch(campaign, *, expected_updated_at):
    validate_launch_readiness(campaign)
    now = timezone.now()
    updated = Campaign.objects.filter(
        pk=campaign.pk,
        updated_at=expected_updated_at,
        status__in=legal_sources_for(CampaignStatus.LIVE),
    ).update(status=CampaignStatus.LIVE, updated_at=now)
    if not updated:
        _diagnose_write_failure(campaign.pk, expected_updated_at)
    campaign.refresh_from_db()
    return campaign


@transaction.atomic
def end(campaign, *, expected_updated_at):
    now = timezone.now()
    updated = Campaign.objects.filter(
        pk=campaign.pk,
        updated_at=expected_updated_at,
        status__in=legal_sources_for(CampaignStatus.ENDED),
    ).update(status=CampaignStatus.ENDED, updated_at=now)
    if not updated:
        _diagnose_write_failure(campaign.pk, expected_updated_at)
    campaign.refresh_from_db()
    return campaign


def enroll(campaign, raw_identity):
    if campaign.status != CampaignStatus.LIVE:
        raise CampaignNotEnrollableError("This campaign is not open for enrollment.")
    normalized, identity_type = normalize_identity(raw_identity)
    # The unique constraint on (campaign, normalized_identity) is the race-safe
    # backstop; get_or_create retries as a get() if it loses a concurrent insert.
    enrollment, created = Enrollment.objects.get_or_create(
        campaign=campaign,
        normalized_identity=normalized,
        defaults={"raw_identity": raw_identity.strip(), "identity_type": identity_type},
    )
    return enrollment, created
