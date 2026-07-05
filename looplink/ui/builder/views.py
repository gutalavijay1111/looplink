import copy
from datetime import datetime

from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView

from looplink.campaigns import activity_cache, selectors, services
from looplink.campaigns.exceptions import CampaignError, CampaignValidationError
from looplink.campaigns.forms import OFFER_FORMS, CampaignDetailsForm
from looplink.campaigns.models import Campaign, CampaignStatus, OfferType
from looplink.campaigns.utilities import distribution_url, qr_code_data_uri
from looplink.django_ext.htmx import DjangoHtmxActionMixin, dj_hx_action

DEFAULT_OFFER_TYPE = OfferType.PRODUCT_PERCENT_DISCOUNT


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


def _offer_forms(*, offer_type=None, bound_form=None):
    """One form instance per offer type, so Alpine can show/hide sections client-side
    without a round trip. Only the type actually submitted (on a validation error)
    is bound; the rest render blank, matching pre-Forms behavior."""
    return {
        ot: bound_form if bound_form is not None and ot == offer_type else form_cls()
        for ot, form_cls in OFFER_FORMS.items()
    }


def _build_context(
    request,
    campaign,
    *,
    error_message=None,
    field_errors=None,
    details_form=None,
    offer_type=None,
    offer_form=None,
    flash=None,
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
        "details_form": details_form or CampaignDetailsForm(instance=campaign),
        "offer_type": offer_type or DEFAULT_OFFER_TYPE,
        "offer_forms": _offer_forms(offer_type=offer_type, bound_form=offer_form),
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
        # A copy, not `campaign` itself: ModelForm validation (construct_instance)
        # mutates the instance it's bound to even when the form is invalid, and
        # `campaign` is also used below to render the page header/etc. — mutating
        # it in place would show unsaved values as if they'd already been saved.
        form = CampaignDetailsForm(request.POST, instance=copy.copy(campaign))
        if not form.is_valid():
            return self._render_body(request, campaign, details_form=form)
        try:
            campaign = services.update_details(
                campaign,
                expected_updated_at=_parse_expected_updated_at(request),
                name=form.cleaned_data["name"],
                description=form.cleaned_data["description"],
                starts_at=form.cleaned_data["starts_at"],
                ends_at=form.cleaned_data["ends_at"],
            )
        except CampaignValidationError as exc:
            # Backstop for races the form's pre-check can't see (e.g. another
            # request claimed the name between validation and this save).
            for field, messages in exc.errors.items():
                for message in messages:
                    form.add_error(field if field in form.fields else None, message)
            return self._render_body(request, campaign, details_form=form)
        except CampaignError as exc:
            return self._render_body(request, campaign, error_message=str(exc))
        return self._render_body(request, campaign, flash="Saved")

    @dj_hx_action("post")
    def add_offer(self, request, *args, **kwargs):
        campaign = self.get_campaign()
        offer_type = request.POST.get("offer_type", "")
        form_cls = OFFER_FORMS.get(offer_type)
        if form_cls is None:
            return self._render_body(request, campaign, error_message=f"Unknown offer type: {offer_type}")
        form = form_cls(request.POST)
        if not form.is_valid():
            return self._render_body(request, campaign, offer_type=offer_type, offer_form=form)
        try:
            services.add_offer(
                campaign,
                expected_updated_at=_parse_expected_updated_at(request),
                offer_type=offer_type,
                params=form.cleaned_data,
            )
        except CampaignValidationError as exc:
            for field, messages in exc.errors.items():
                for message in messages:
                    form.add_error(field if field in form.fields else None, message)
            return self._render_body(request, campaign, offer_type=offer_type, offer_form=form)
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
