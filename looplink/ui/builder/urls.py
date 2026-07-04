from django.urls import path

from looplink.ui.builder.views import CampaignDetailView, CampaignListView

urlpatterns = [
    path("", CampaignListView.as_view(), name=CampaignListView.urlname),
    path("<int:pk>/", CampaignDetailView.as_view(), name=CampaignDetailView.urlname),
]
