from django.urls import path

from .views import ClassLeaderboardView, StudentClassListView


urlpatterns = [
    path(
        "classes/",
        StudentClassListView.as_view(),
        name="student-class-list",
    ),
    path(
        "classes/<int:pk>/leaderboard/",
        ClassLeaderboardView.as_view(),
        name="class-leaderboard",
    ),
]