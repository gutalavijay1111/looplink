from django.urls import path

from looplink.ui.shopper.views import CampaignView

urlpatterns = [
    path("c/<str:token>/", CampaignView.as_view(), name=CampaignView.urlname),
]
