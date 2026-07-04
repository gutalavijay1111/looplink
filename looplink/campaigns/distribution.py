import base64
from io import BytesIO

import segno
from django.urls import reverse


def distribution_path(campaign):
    return reverse("shopper_campaign", args=[campaign.token])


def distribution_url(request, campaign):
    return request.build_absolute_uri(distribution_path(campaign))


def qr_code_data_uri(url):
    """PNG data URI for the given URL, suitable for an inline <img src>."""
    buffer = BytesIO()
    segno.make(url, error="m").save(buffer, kind="png", scale=6, border=2)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
