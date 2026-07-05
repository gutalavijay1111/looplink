from decimal import Decimal

from django import forms

from looplink.campaigns.exceptions import CampaignValidationError
from looplink.campaigns.identity import normalize_identity
from looplink.campaigns.models import NAME_ALREADY_EXISTS_MSG, Campaign, OfferType

FIELD_INPUT_ATTRS = {"class": "field-input"}

REQUIRED_MSG = "This field is required."
POSITIVE_MSG = "Must be greater than 0."
NON_NEGATIVE_MSG = "Must be 0 or greater."
END_AFTER_START_MSG = "End must be after start."
PERCENT_MAX = 100


def max_value_msg(max_value):
    return f"Must be at most {max_value}."


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
        # The model's UniqueConstraint(Lower("name")) is the authoritative backstop
        # (validated again on save); this pre-check just attaches the error to the
        # right field instead of the form-wide "__all__" bucket Django would use.
        name = self.cleaned_data["name"].strip()
        conflicts = Campaign.objects.filter(name__iexact=name)
        if self.instance.pk is not None:
            conflicts = conflicts.exclude(pk=self.instance.pk)
        if conflicts.exists():
            raise forms.ValidationError(NAME_ALREADY_EXISTS_MSG)
        return name

    def clean(self):
        cleaned = super().clean()
        starts_at, ends_at = cleaned.get("starts_at"), cleaned.get("ends_at")
        if starts_at and ends_at and ends_at <= starts_at:
            self.add_error("ends_at", END_AFTER_START_MSG)
        return cleaned


def _offer_attrs(offer_type):
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
    return {**FIELD_INPUT_ATTRS, "x-bind:required": f"offerType === '{offer_type}'"}


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
    percent = forms.DecimalField(
        min_value=Decimal("0.01"),
        max_value=PERCENT_MAX,
        decimal_places=2,
        error_messages={"min_value": POSITIVE_MSG, "max_value": max_value_msg(PERCENT_MAX)},
        widget=forms.NumberInput(attrs=_offer_attrs(OfferType.PRODUCT_PERCENT_DISCOUNT)),
    )
    applies_to = forms.CharField(
        error_messages={"required": REQUIRED_MSG},
        widget=forms.TextInput(attrs=_offer_attrs(OfferType.PRODUCT_PERCENT_DISCOUNT)),
    )


class CartFixedDiscountOfferForm(_OfferForm):
    amount_off = forms.DecimalField(
        min_value=Decimal("0.01"),
        decimal_places=2,
        error_messages={"min_value": POSITIVE_MSG},
        widget=forms.NumberInput(attrs=_offer_attrs(OfferType.CART_FIXED_DISCOUNT)),
    )
    min_basket = forms.DecimalField(
        min_value=Decimal("0"),
        decimal_places=2,
        error_messages={"min_value": NON_NEGATIVE_MSG},
        widget=forms.NumberInput(attrs=_offer_attrs(OfferType.CART_FIXED_DISCOUNT)),
    )


class StickerEarnOfferForm(_OfferForm):
    stickers = forms.IntegerField(
        min_value=1,
        error_messages={"min_value": POSITIVE_MSG},
        widget=forms.NumberInput(attrs=_offer_attrs(OfferType.STICKER_EARN)),
    )
    per_amount = forms.DecimalField(
        min_value=Decimal("0.01"),
        decimal_places=2,
        error_messages={"min_value": POSITIVE_MSG},
        widget=forms.NumberInput(attrs=_offer_attrs(OfferType.STICKER_EARN)),
    )


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
