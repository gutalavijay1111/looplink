import pytest
from django.test import RequestFactory

from looplink.campaigns.distribution import distribution_path, distribution_url, qr_code_data_uri

pytestmark = pytest.mark.django_db


def test_distribution_path_encodes_token_not_pk(make_campaign):
    campaign = make_campaign()

    path = distribution_path(campaign)

    assert path == f"/c/{campaign.token}/"
    assert str(campaign.pk) not in path


def test_distribution_url_is_absolute(make_campaign):
    campaign = make_campaign()
    request = RequestFactory().get("/")

    url = distribution_url(request, campaign)

    assert url == f"http://testserver/c/{campaign.token}/"


def test_qr_code_data_uri_is_a_png_data_uri():
    data_uri = qr_code_data_uri("http://testserver/c/abc123/")

    assert data_uri.startswith("data:image/png;base64,")
    assert len(data_uri) > len("data:image/png;base64,")
