from django.urls import path

from . import views

urlpatterns = [
    path("lectures/", views.LectureListView.as_view(), name="lecture-list"),
    path("lectures/<int:pk>/quiz/", views.LectureQuizView.as_view(), name="lecture-quiz"),
]
