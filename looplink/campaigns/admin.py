from django.contrib import admin

from looplink.campaigns.models import Campaign, Enrollment, Offer


class OfferInline(admin.TabularInline):
    model = Offer
    extra = 0


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0
    readonly_fields = ["raw_identity", "normalized_identity", "identity_type", "created_at"]


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ["name", "status", "starts_at", "ends_at", "updated_at"]
    list_filter = ["status"]
    readonly_fields = ["token", "created_at", "updated_at"]
    inlines = [OfferInline, EnrollmentInline]
