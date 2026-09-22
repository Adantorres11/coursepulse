from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    # Sprint 1 (backend ticket): include quiz endpoints here, e.g. path("api/", include("quizzes.urls")).
]
