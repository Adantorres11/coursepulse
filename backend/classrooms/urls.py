from django.urls import path

from .views import (
    ClassJoinView,
    ClassLookupView,
    StudentClassListView,
)

urlpatterns = [
    path(
        "classes/",
        StudentClassListView.as_view(),
        name="student-class-list",
    ),
    path(
        "classes/lookup/",
        ClassLookupView.as_view(),
        name="class-lookup",
    ),
    path(
        "classes/join/",
        ClassJoinView.as_view(),
        name="class-join",
    ),
]