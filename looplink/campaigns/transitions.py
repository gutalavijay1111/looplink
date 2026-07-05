from looplink.campaigns.models import CampaignStatus

# Single source of truth for which status changes are legal. Both the read-side
# (selectors.can_schedule/can_launch/can_end, for UI rendering) and the write-side
# (services.schedule/launch/end, for enforcement) read from this table, so the two
# can't drift apart the way two independently hand-written status lists could.
LEGAL_TRANSITIONS = {
    CampaignStatus.DRAFT: frozenset({CampaignStatus.SCHEDULED, CampaignStatus.LIVE}),
    CampaignStatus.SCHEDULED: frozenset({CampaignStatus.LIVE}),
    CampaignStatus.LIVE: frozenset({CampaignStatus.ENDED}),
    CampaignStatus.ENDED: frozenset(),
}


def is_legal_transition(from_status, to_status):
    return to_status in LEGAL_TRANSITIONS.get(from_status, frozenset())


def legal_sources_for(to_status):
    """Statuses a campaign may legally be in right now to reach to_status next."""
    return frozenset(from_status for from_status, targets in LEGAL_TRANSITIONS.items() if to_status in targets)


# Also a single source of truth: selectors.can_edit, services' draft-only write
# guards, and Campaign.clean()'s model-level backstop all read this instead of
# each hand-writing their own "== CampaignStatus.DRAFT" copy of the same rule.
EDITABLE_STATUSES = frozenset({CampaignStatus.DRAFT})


def is_editable(status):
    return status in EDITABLE_STATUSES
