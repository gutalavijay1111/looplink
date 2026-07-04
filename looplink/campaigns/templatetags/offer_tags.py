from django import template
from django.template.defaultfilters import floatformat

from looplink.campaigns.models import OfferType

register = template.Library()


def _number(value):
    return floatformat(value, "-2")


@register.simple_tag
def offer_summary(offer):
    """
    Human-readable summary of an offer's parameters — the single place both the
    builder and the shopper page turn a params dict into display text, so the
    two surfaces can't drift out of sync on what a shopper is promised.
    """
    params = offer.params
    if offer.offer_type == OfferType.PRODUCT_PERCENT_DISCOUNT:
        return f"{_number(params.get('percent'))}% off {params.get('applies_to', '')}"
    if offer.offer_type == OfferType.CART_FIXED_DISCOUNT:
        return f"${_number(params.get('amount_off'))} off orders over ${_number(params.get('min_basket'))}"
    if offer.offer_type == OfferType.STICKER_EARN:
        stickers = params.get("stickers")
        plural = "" if stickers == 1 else "s"
        return f"Earn {stickers} sticker{plural} per ${_number(params.get('per_amount'))} spent"
    return ""
