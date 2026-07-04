from looplink.campaigns.models import Offer, OfferType
from looplink.campaigns.templatetags.offer_tags import offer_summary


def _offer(offer_type, params):
    return Offer(offer_type=offer_type, params=params)


def test_percent_discount_summary_trims_trailing_zero():
    offer = _offer(OfferType.PRODUCT_PERCENT_DISCOUNT, {"percent": 15.0, "applies_to": "Snacks"})

    assert offer_summary(offer) == "15% off Snacks"


def test_cart_fixed_discount_summary():
    offer = _offer(OfferType.CART_FIXED_DISCOUNT, {"amount_off": 5, "min_basket": 20.5})

    assert offer_summary(offer) == "$5 off orders over $20.50"


def test_sticker_earn_summary_singular():
    offer = _offer(OfferType.STICKER_EARN, {"stickers": 1, "per_amount": 10})

    assert offer_summary(offer) == "Earn 1 sticker per $10 spent"


def test_sticker_earn_summary_plural():
    offer = _offer(OfferType.STICKER_EARN, {"stickers": 2, "per_amount": 10})

    assert offer_summary(offer) == "Earn 2 stickers per $10 spent"
