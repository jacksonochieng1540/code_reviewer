from django.urls import path

from . import views

app_name = "reviewer"

urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
]

api_urlpatterns = [
    path("reviews/", views.CodeReviewCreateView.as_view(), name="review-create"),
    path("reviews/list/", views.CodeReviewListView.as_view(), name="review-list"),
    path("reviews/<uuid:pk>/", views.CodeReviewDetailView.as_view(), name="review-detail"),
]
