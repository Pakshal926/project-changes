# Generated by Django 4.2.11 on 2024-10-31 09:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscription",
            name="subscription_tier",
            field=models.CharField(
                choices=[("standard", "Standard"), ("advanced", "Advanced")],
                default="standard",
                max_length=20,
            ),
        ),
    ]
