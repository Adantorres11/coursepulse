import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quizzes", "0015_lecture_notice_question_generation"),
    ]

    operations = [
        migrations.AddField(
            model_name="lecture",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
    ]
