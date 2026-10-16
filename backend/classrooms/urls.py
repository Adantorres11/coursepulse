from django.urls import path

from .views import StudentClassListView

urlpatterns = [
    path(
        "classes/",
        StudentClassListView.as_view(),
        name="student-class-list",
    ),
]