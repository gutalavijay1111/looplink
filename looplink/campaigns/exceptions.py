class CampaignError(Exception):
    """Base class for all campaigns-domain errors."""


class CampaignValidationError(CampaignError):
    """Field-level validation failure. ``errors`` maps field name to a list of messages."""

    def __init__(self, errors):
        if isinstance(errors, str):
            errors = {"__all__": [errors]}
        self.errors = errors
        super().__init__(str(errors))


class CampaignLockedError(CampaignError):
    """Raised when editing is attempted on a campaign that is not in draft."""


class IllegalTransitionError(CampaignError):
    """Raised when a schedule/launch/end transition isn't legal from the current status."""


class StaleCampaignError(CampaignError):
    """Raised when a mutation's expected_updated_at no longer matches the stored row."""


class CampaignNotEnrollableError(CampaignError):
    """Raised when enrollment is attempted on a campaign that isn't live."""
