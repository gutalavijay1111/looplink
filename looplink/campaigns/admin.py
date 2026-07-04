from django.contrib import admin

from looplink.campaigns.models import Campaign, Enrollment, Offer


class ReadOnlyInlineMixin:
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class OfferInline(ReadOnlyInlineMixin, admin.TabularInline):
    model = Offer


class EnrollmentInline(ReadOnlyInlineMixin, admin.TabularInline):
    model = Enrollment
    readonly_fields = ["raw_identity", "normalized_identity", "identity_type", "created_at"]


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    """
    Inspection only. Every rule that matters (legal transitions, draft-only
    editing, stale-edit protection) lives in campaigns.services, which nothing
    here calls — Django admin writes straight to the ORM. Rather than
    reimplementing that state machine a second time for a surface the spec
    never asked for, admin editing is disabled outright.
    """

    list_display = ["name", "status", "starts_at", "ends_at", "updated_at"]
    list_filter = ["status"]
    readonly_fields = ["token", "created_at", "updated_at"]
    inlines = [OfferInline, EnrollmentInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
