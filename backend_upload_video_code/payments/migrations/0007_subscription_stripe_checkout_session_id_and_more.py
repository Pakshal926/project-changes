# Generated by Django 4.2.11 on 2024-11-13 05:29

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("payments", "0006_alter_subscription_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscription",
            name="stripe_checkout_session_id",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="subscription",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="subscription",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
