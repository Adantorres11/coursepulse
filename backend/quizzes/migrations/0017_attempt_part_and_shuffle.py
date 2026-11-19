from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quizzes", "0016_lecture_created_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="attempt",
            name="part_index",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="attempt",
            name="question_order",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="attempt",
            name="choice_orders",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RemoveConstraint(
            model_name="attempt",
            name="unique_open_attempt_per_user_lecture",
        ),
        migrations.AddConstraint(
            model_name="attempt",
            constraint=models.UniqueConstraint(
                condition=models.Q(("completed_at__isnull", True)),
                fields=("user", "lecture", "part_index"),
                name="unique_open_attempt_per_user_lecture_part",
            ),
        ),
    ]
