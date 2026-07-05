from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower

from looplink.campaigns.exceptions import CampaignValidationError
from looplink.campaigns.tokens import generate_campaign_token


class CampaignStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SCHEDULED = "scheduled", "Scheduled"
    LIVE = "live", "Live"
    ENDED = "ended", "Ended"


class OfferType(models.TextChoices):
    PRODUCT_PERCENT_DISCOUNT = "PRODUCT_PERCENT_DISCOUNT", "Product percent discount"
    CART_FIXED_DISCOUNT = "CART_FIXED_DISCOUNT", "Cart fixed discount"
    STICKER_EARN = "STICKER_EARN", "Sticker earn"


class IdentityType(models.TextChoices):
    EMAIL = "email", "Email"
    PHONE = "phone", "Phone"


# Shared with CampaignDetailsForm.clean_name (looplink.campaigns.forms), which checks this same
# case-insensitive rule ahead of the DB round trip; the constraint below is the actual backstop.
NAME_ALREADY_EXISTS_MSG = "A campaign with this name already exists."


class Campaign(models.Model):
    # Fields that may only change while the campaign is still in an editable
    # (draft) status — Campaign.clean() below blocks a save that touches any of
    # these once the campaign has moved on, regardless of caller.
    LOCKED_FIELDS = frozenset({"name", "description", "starts_at", "ends_at"})

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=CampaignStatus.choices,
        default=CampaignStatus.DRAFT,
    )
    token = models.CharField(max_length=32, unique=True, default=generate_campaign_token, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    # Used as the optimistic-concurrency check for stale edits: a save is only
    # applied if the client's last-seen updated_at still matches this value.
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="unique_campaign_name_ci",
                violation_error_message=NAME_ALREADY_EXISTS_MSG,
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.status})"

    def save(self, *args, **kwargs):
        # Inert for every write this app's own services.py makes (those are all
        # QuerySet.update() calls, which never touch save()/clean() at all — see
        # TECH_NOTES). This is the backstop for everything else: Django admin,
        # a shell session, a data migration, a future direct `obj.save()`.
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        # Local import: transitions.py imports CampaignStatus from this module,
        # so importing it back at module level here would be circular.
        from looplink.campaigns.transitions import is_editable, is_legal_transition
        from looplink.campaigns.validators import validate_launch_readiness

        if not self.pk:
            return
        # Fetched fresh rather than cached on the instance at load time: caching
        # (e.g. in __init__/from_db) goes stale the moment anything calls
        # refresh_from_db(), which updates fields in place without going through
        # either of those hooks — services.py does exactly that after every
        # mutation, so a cached baseline would silently stop being checked.
        current = Campaign.objects.get(pk=self.pk)
        if self.status != current.status:
            if not is_legal_transition(current.status, self.status):
                raise ValidationError({"status": f"Cannot go from {current.status} to {self.status}."})
            if self.status in (CampaignStatus.SCHEDULED, CampaignStatus.LIVE):
                # Same check services.schedule()/launch() already run before their
                # atomic update — reused here, not reimplemented, so "what makes a
                # campaign launch-ready" only has one definition.
                try:
                    validate_launch_readiness(self)
                except CampaignValidationError as exc:
                    raise ValidationError(exc.errors) from None
        if not is_editable(current.status):
            changed = {field for field in self.LOCKED_FIELDS if getattr(self, field) != getattr(current, field)}
            if changed:
                raise ValidationError("This campaign can no longer be edited.")


class Offer(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="offers")
    offer_type = models.CharField(max_length=32, choices=OfferType.choices)
    # Parameters are shaped per offer_type (see campaigns.validators); kept as JSON
    # rather than a wide sparse column set since the catalog isn't relational.
    params = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.offer_type} on campaign #{self.campaign_id}"


class Enrollment(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="enrollments")
    raw_identity = models.CharField(max_length=255)
    normalized_identity = models.CharField(max_length=255, db_index=True)
    identity_type = models.CharField(max_length=10, choices=IdentityType.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "normalized_identity"],
                name="unique_campaign_identity",
            ),
        ]

    def __str__(self):
        return f"{self.normalized_identity} on campaign #{self.campaign_id}"
