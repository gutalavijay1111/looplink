from django.views.generic import TemplateView

from looplink.campaigns import selectors, services
from looplink.campaigns.exceptions import CampaignError
from looplink.campaigns.forms import EnrollForm
from looplink.campaigns.models import CampaignStatus
from looplink.django_ext.htmx import DjangoHtmxActionMixin, dj_hx_action


def _build_context(campaign, *, error_message=None, enroll_form=None, enrolled=False, just_created=False):
    if campaign is None:
        return {"state": "invalid", "campaign": None}
    if campaign.status != CampaignStatus.LIVE:
        return {"state": "not_live", "campaign": campaign}
    return {
        "state": "live",
        "campaign": campaign,
        "offers": campaign.offers.all(),
        "enrolled": enrolled,
        "just_created": just_created,
        "enroll_form": enroll_form or EnrollForm(),
        "error_message": error_message,
    }


class CampaignView(DjangoHtmxActionMixin, TemplateView):
    template_name = "shopper/campaign.html"
    urlname = "shopper_campaign"

    def get_campaign(self):
        return selectors.get_campaign_by_token(self.kwargs["token"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_build_context(self.get_campaign()))
        return context

    def render_to_response(self, context, **response_kwargs):
        if context["state"] == "invalid":
            response_kwargs["status"] = 404
        return super().render_to_response(context, **response_kwargs)

    def _render_body(self, request, campaign, **overrides):
        context = _build_context(campaign, **overrides)
        return self.render_htmx_partial_response(request, "shopper/partials/campaign_body.html", context)

    @dj_hx_action("post")
    def enroll(self, request, *args, **kwargs):
        campaign = self.get_campaign()
        if campaign is None:
            return self._render_body(request, None)

        form = EnrollForm(request.POST)
        if not form.is_valid():
            return self._render_body(request, campaign, enroll_form=form)
        try:
            _enrollment, created = services.enroll(campaign, form.cleaned_data["identity"])
        except CampaignError as exc:
            return self._render_body(request, campaign, error_message=str(exc))
        return self._render_body(request, campaign, enrolled=True, just_created=created)
