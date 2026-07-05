from decimal import Decimal

from django import forms

from looplink.campaigns import validators
from looplink.campaigns.exceptions import CampaignValidationError
from looplink.campaigns.models import Campaign, OfferType
from looplink.campaigns.utilities import normalize_identity

FIELD_INPUT_ATTRS = {"class": "field-input"}


class CampaignDetailsForm(forms.ModelForm):
    """
    The one place campaign-details input is validated: field constraints (required,
    name's max_length) come straight from the Campaign model, so the HTML5 attrs
    rendered from this form can't drift from what the database actually allows.
    `services.update_details` no longer re-validates — it only owns the atomic
    write (optimistic-concurrency check, draft-only lock) — so this form must run
    on every path that saves campaign details.
    """

    class Meta:
        model = Campaign
        fields = ["name", "description", "starts_at", "ends_at"]
        error_messages = {
            "name": {"required": "Name is required."},
            "starts_at": {"required": "Start date is required."},
            "ends_at": {"required": "End date is required."},
        }
        widgets = {
            "name": forms.TextInput(attrs=FIELD_INPUT_ATTRS),
            "description": forms.Textarea(attrs={**FIELD_INPUT_ATTRS, "rows": 2}),
            "starts_at": forms.DateTimeInput(
                attrs={**FIELD_INPUT_ATTRS, "type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "ends_at": forms.DateTimeInput(
                attrs={**FIELD_INPUT_ATTRS, "type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
        }

    def clean_name(self):
        # validators.validate_name_unique is the actual rule; this just supplies
        # the stripped value and the current instance's pk to exclude.
        name = self.cleaned_data["name"].strip()
        validators.validate_name_unique(name, exclude_pk=self.instance.pk)
        return name

    def clean(self):
        cleaned = super().clean()
        starts_at, ends_at = cleaned.get("starts_at"), cleaned.get("ends_at")
        if starts_at and ends_at and ends_at <= starts_at:
            self.add_error("ends_at", validators.END_AFTER_START_MSG)
        return cleaned


def _offer_attrs(offer_type, **extra):
    """
    All three offer-type sections are always in the DOM at once — Alpine's
    x-show just toggles `display:none` on whichever two aren't selected — so a
    plain `required` on every field would make the browser try to validate
    inputs it can't even show the user, which silently blocks submission with
    no visible error (a hidden field can't be focused to report why it failed).
    Binding `required` to the same `offerType` Alpine already tracks keeps
    exactly one section's fields required at a time, in the DOM the form
    actually renders — not a second, independent copy of "which type is active."
    """
    return {**FIELD_INPUT_ATTRS, "x-bind:required": f"offerType === '{offer_type}'", **extra}


class _OfferForm(forms.Form):
    """
    Offer.params is a JSONField shaped differently per offer_type, so there's no
    single model to hang a ModelForm off of — these stay plain Forms, one per type.
    DecimalField.clean() returns Decimal, which json.JSONEncoder can't serialize,
    so cast back to float here (once) rather than in every caller.
    """

    def clean(self):
        cleaned = super().clean()
        return {key: float(value) if isinstance(value, Decimal) else value for key, value in cleaned.items()}


class PercentDiscountOfferForm(_OfferForm):
    # No min_value/max_value on the field itself — validators.validate_positive is
    # the one place that decides "acceptable," called from clean_percent() below.
    # The widget's min/max attrs are set from that same PERCENT_MAX constant, so
    # the browser's native check and the server check can't drift apart.
    percent = forms.DecimalField(
        decimal_places=2,
        widget=forms.NumberInput(
            attrs=_offer_attrs(
                OfferType.PRODUCT_PERCENT_DISCOUNT, min="0.01", max=str(validators.PERCENT_MAX), step="0.01"
            )
        ),
    )
    applies_to = forms.CharField(
        error_messages={"required": validators.REQUIRED_MSG},
        widget=forms.TextInput(attrs=_offer_attrs(OfferType.PRODUCT_PERCENT_DISCOUNT)),
    )

    def clean_percent(self):
        return validators.validate_positive(self.cleaned_data.get("percent"), max_value=validators.PERCENT_MAX)


class CartFixedDiscountOfferForm(_OfferForm):
    amount_off = forms.DecimalField(
        decimal_places=2,
        widget=forms.NumberInput(
            attrs=_offer_attrs(OfferType.CART_FIXED_DISCOUNT, min="0.01", step="0.01"),
        ),
    )
    min_basket = forms.DecimalField(
        decimal_places=2,
        widget=forms.NumberInput(
            attrs=_offer_attrs(OfferType.CART_FIXED_DISCOUNT, min="0", step="0.01"),
        ),
    )

    def clean_amount_off(self):
        return validators.validate_positive(self.cleaned_data.get("amount_off"))

    def clean_min_basket(self):
        return validators.validate_non_negative(self.cleaned_data.get("min_basket"))


class StickerEarnOfferForm(_OfferForm):
    stickers = forms.IntegerField(
        widget=forms.NumberInput(attrs=_offer_attrs(OfferType.STICKER_EARN, min="1", step="1")),
    )
    per_amount = forms.DecimalField(
        decimal_places=2,
        widget=forms.NumberInput(
            attrs=_offer_attrs(OfferType.STICKER_EARN, min="0.01", step="0.01"),
        ),
    )

    def clean_stickers(self):
        return validators.validate_positive(self.cleaned_data.get("stickers"))

    def clean_per_amount(self):
        return validators.validate_positive(self.cleaned_data.get("per_amount"))


OFFER_FORMS = {
    OfferType.PRODUCT_PERCENT_DISCOUNT: PercentDiscountOfferForm,
    OfferType.CART_FIXED_DISCOUNT: CartFixedDiscountOfferForm,
    OfferType.STICKER_EARN: StickerEarnOfferForm,
}


class EnrollForm(forms.Form):
    """
    Enrollment's raw_identity/normalized_identity/identity_type don't map 1:1 onto
    a single "identity" input, so this stays a plain Form; normalize_identity is
    the one function that decides what's a valid phone/email, called here for the
    early check and again in services.enroll to get the value it needs to persist.
    """

    identity = forms.CharField(
        error_messages={"required": "Enter a phone number or email address."},
        widget=forms.TextInput(
            attrs={
                **FIELD_INPUT_ATTRS,
                "placeholder": "you@example.com",
                "inputmode": "email",
                "autocomplete": "email",
            }
        ),
    )

    def clean_identity(self):
        raw = self.cleaned_data["identity"]
        try:
            normalize_identity(raw)
        except CampaignValidationError as exc:
            raise forms.ValidationError(exc.errors["identity"][0]) from None
        return raw.strip()
