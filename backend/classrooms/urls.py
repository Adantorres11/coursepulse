from django.urls import path

from .views import (
    ClassJoinView,
    ClassLeaderboardView,
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
    path(
        "classes/<int:pk>/leaderboard/",
        ClassLeaderboardView.as_view(),
        name="class-leaderboard",
    ),
]
