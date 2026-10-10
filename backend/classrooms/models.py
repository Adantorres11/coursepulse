from django.conf import settings
from django.db import models


class Classroom(models.Model):
    name = models.CharField(max_length=255)
    course_code = models.CharField(max_length=50, blank=True)
    professor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="taught_classrooms",
    )

    def __str__(self):
        return self.name


class Enrollment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "classroom"],
                name="unique_user_classroom_enrollment",
            ),
        ]

    def __str__(self):
        return f"{self.user_id} enrolled in {self.classroom.name}"