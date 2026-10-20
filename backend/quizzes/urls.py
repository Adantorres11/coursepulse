from django.urls import path

from . import views

urlpatterns = [
    path("lectures/", views.LectureListView.as_view(), name="lecture-list"),
]
