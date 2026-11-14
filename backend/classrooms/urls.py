
from django.urls import path

from .views import (
    ClassJoinView,
    ClassLeaderboardView,
    ClassLookupView,
    ClassStatsView,
    StudentClassListView,
    ProfessorClassListView,
    ClassResultsView,
    ClassRosterView,
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
    path(
        "classes/<int:pk>/stats/",
        ClassStatsView.as_view(),
        name="class-stats",
    ),
    path(
        "professor/classes/",
        ProfessorClassListView.as_view(),
        name="professor-class-list",
    ),
    path(
        "classes/<int:pk>/results/",
        ClassResultsView.as_view(),
        name="class-results",
    ),
    path(
        "classes/<int:pk>/roster/",
        ClassRosterView.as_view(),
        name="class-roster",
    ),
]