from django.db import models

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


class Campaign(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=CampaignStatus.choices,
        default=CampaignStatus.DRAFT,
    )
    # Generated eagerly so a distribution link/QR can be produced without a schema
    # change once the campaign goes live; resolving it while non-live just renders
    # the appropriate non-live state rather than the offers.
    token = models.CharField(max_length=32, unique=True, default=generate_campaign_token, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    # Used as the optimistic-concurrency check for stale edits: a save is only
    # applied if the client's last-seen updated_at still matches this value.
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.status})"


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
