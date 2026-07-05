from django.contrib import admin

from looplink.campaigns.forms import CampaignAdminForm
from looplink.campaigns.models import Campaign, Enrollment, Offer


class OfferInline(admin.TabularInline):
    model = Offer


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    readonly_fields = ["raw_identity", "normalized_identity", "identity_type", "created_at"]


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    """
    Admin writes go straight to the ORM, bypassing campaigns.services entirely —
    but Campaign.clean()/save() enforce legal transitions, draft-only editing,
    and launch readiness at the model level, so an illegal edit here is rejected
    the same as it would be anywhere else.
    """

    form = CampaignAdminForm
    list_display = ["name", "status", "starts_at", "ends_at", "updated_at"]
    list_filter = ["status"]
    readonly_fields = ["token", "created_at", "updated_at"]
    inlines = [OfferInline, EnrollmentInline]
