from datetime import datetime

from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone as dj_timezone
from django.views.generic import TemplateView

from looplink.campaigns import activity_cache, selectors, services
from looplink.campaigns.distribution import distribution_url, qr_code_data_uri
from looplink.campaigns.exceptions import CampaignError, CampaignValidationError
from looplink.campaigns.models import Campaign, CampaignStatus, OfferType
from looplink.django_ext.htmx import DjangoHtmxActionMixin, dj_hx_action

OFFER_PARAM_FIELDS = {
    OfferType.PRODUCT_PERCENT_DISCOUNT: ["percent", "applies_to"],
    OfferType.CART_FIXED_DISCOUNT: ["amount_off", "min_basket"],
    OfferType.STICKER_EARN: ["stickers", "per_amount"],
}


class CampaignListView(TemplateView):
    template_name = "builder/campaign_list.html"
    urlname = "builder_campaign_list"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["campaign_rows"] = [
            {"campaign": campaign, "offer_count": campaign.offers.count()} for campaign in selectors.list_campaigns()
        ]
        return context

    def post(self, request, *args, **kwargs):
        campaign = services.create_draft()
        return redirect("builder_campaign_detail", pk=campaign.pk)


def _parse_expected_updated_at(request):
    raw = request.POST.get("expected_updated_at", "")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _parse_local_datetime(value, field_name):
    if not value:
        raise CampaignValidationError({field_name: ["This field is required."]})
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise CampaignValidationError({field_name: ["Enter a valid date and time."]}) from None
    if dj_timezone.is_naive(parsed):
        parsed = dj_timezone.make_aware(parsed)
    return parsed


def _default_details_values(campaign):
    return {
        "name": campaign.name,
        "description": campaign.description,
        "starts_at": campaign.starts_at.strftime("%Y-%m-%dT%H:%M"),
        "ends_at": campaign.ends_at.strftime("%Y-%m-%dT%H:%M"),
    }


def _build_distribution(request, campaign):
    if campaign.status != CampaignStatus.LIVE:
        return None
    url = distribution_url(request, campaign)
    return {"url": url, "qr_data_uri": qr_code_data_uri(url)}


def _build_live_activity(campaign, *, polling=False):
    if campaign.status != CampaignStatus.LIVE:
        return None
    return {
        "polling": polling,
        "count": activity_cache.get_enrollment_count(campaign),
        "recent": activity_cache.get_recent_enrollments(campaign),
    }


def _build_context(
    request, campaign, *, error_message=None, field_errors=None, details_values=None, offer_values=None, flash=None
):
    return {
        "campaign": campaign,
        "offers": campaign.offers.all(),
        "transitions": selectors.available_transitions(campaign),
        "enrollment_count": selectors.enrollment_count(campaign),
        "distribution": _build_distribution(request, campaign),
        # Page load always starts paused: nothing polls until a viewer opts in
        # by clicking "View live", so an idle open tab costs nothing.
        "live_activity": _build_live_activity(campaign, polling=False),
        "error_message": error_message,
        "field_errors": field_errors or {},
        "details_values": details_values or _default_details_values(campaign),
        "offer_values": offer_values or {},
        "flash": flash,
    }


class CampaignDetailView(DjangoHtmxActionMixin, TemplateView):
    template_name = "builder/campaign_detail.html"
    urlname = "builder_campaign_detail"

    def get_campaign(self):
        return get_object_or_404(Campaign, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_build_context(self.request, self.get_campaign()))
        return context

    def _render_body(self, request, campaign, **overrides):
        context = _build_context(request, campaign, **overrides)
        return self.render_htmx_partial_response(request, "builder/partials/campaign_body.html", context)

    def _render_activity(self, request, campaign, *, polling):
        return self.render_htmx_partial_response(
            request,
            "builder/partials/live_activity.html",
            {"campaign": campaign, "live_activity": _build_live_activity(campaign, polling=polling)},
        )

    @dj_hx_action("get")
    def activity(self, request, *args, **kwargs):
        """
        Starts live view (button click) and keeps it going (each 5s poll hits
        this same action) — the returned fragment re-declares its own polling
        trigger, so it keeps ticking until activity_stop renders it away.
        """
        return self._render_activity(request, self.get_campaign(), polling=True)

    @dj_hx_action("get")
    def activity_stop(self, request, *args, **kwargs):
        return self._render_activity(request, self.get_campaign(), polling=False)

    @dj_hx_action("post")
    def save_details(self, request, *args, **kwargs):
        campaign = self.get_campaign()
        details_values = {
            "name": request.POST.get("name", ""),
            "description": request.POST.get("description", ""),
            "starts_at": request.POST.get("starts_at", ""),
            "ends_at": request.POST.get("ends_at", ""),
        }
        try:
            starts_at = _parse_local_datetime(details_values["starts_at"], "starts_at")
            ends_at = _parse_local_datetime(details_values["ends_at"], "ends_at")
            campaign = services.update_details(
                campaign,
                expected_updated_at=_parse_expected_updated_at(request),
                name=details_values["name"],
                description=details_values["description"],
                starts_at=starts_at,
                ends_at=ends_at,
            )
        except CampaignValidationError as exc:
            return self._render_body(request, campaign, field_errors=exc.errors, details_values=details_values)
        except CampaignError as exc:
            return self._render_body(request, campaign, error_message=str(exc))
        return self._render_body(request, campaign, flash="Saved")

    @dj_hx_action("post")
    def add_offer(self, request, *args, **kwargs):
        campaign = self.get_campaign()
        offer_type = request.POST.get("offer_type", "")
        fields = OFFER_PARAM_FIELDS.get(offer_type, [])
        params = {field: request.POST.get(field, "") for field in fields}
        try:
            services.add_offer(
                campaign,
                expected_updated_at=_parse_expected_updated_at(request),
                offer_type=offer_type,
                params=params,
            )
        except CampaignValidationError as exc:
            offer_values = {"offer_type": offer_type, **params}
            return self._render_body(request, campaign, field_errors=exc.errors, offer_values=offer_values)
        except CampaignError as exc:
            return self._render_body(request, campaign, error_message=str(exc))
        return self._render_body(request, campaign, flash="Offer added")

    @dj_hx_action("post")
    def remove_offer(self, request, *args, **kwargs):
        campaign = self.get_campaign()
        try:
            services.remove_offer(
                campaign,
                expected_updated_at=_parse_expected_updated_at(request),
                offer_id=request.POST.get("offer_id"),
            )
        except CampaignError as exc:
            return self._render_body(request, campaign, error_message=str(exc))
        return self._render_body(request, campaign, flash="Offer removed")

    @dj_hx_action("post")
    def schedule(self, request, *args, **kwargs):
        campaign = self.get_campaign()
        try:
            campaign = services.schedule(campaign, expected_updated_at=_parse_expected_updated_at(request))
        except CampaignValidationError as exc:
            return self._render_body(request, campaign, field_errors=exc.errors)
        except CampaignError as exc:
            return self._render_body(request, campaign, error_message=str(exc))
        return self._render_body(request, campaign)

    @dj_hx_action("post")
    def launch(self, request, *args, **kwargs):
        campaign = self.get_campaign()
        try:
            campaign = services.launch(campaign, expected_updated_at=_parse_expected_updated_at(request))
        except CampaignValidationError as exc:
            return self._render_body(request, campaign, field_errors=exc.errors)
        except CampaignError as exc:
            return self._render_body(request, campaign, error_message=str(exc))
        return self._render_body(request, campaign)

    @dj_hx_action("post")
    def end(self, request, *args, **kwargs):
        campaign = self.get_campaign()
        try:
            campaign = services.end(campaign, expected_updated_at=_parse_expected_updated_at(request))
        except CampaignError as exc:
            return self._render_body(request, campaign, error_message=str(exc))
        return self._render_body(request, campaign)
