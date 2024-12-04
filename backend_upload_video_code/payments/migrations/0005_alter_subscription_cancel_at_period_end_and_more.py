# Generated by Django 4.2.11 on 2024-11-11 10:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0004_alter_subscription_current_period_end_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="subscription",
            name="cancel_at_period_end",
            field=models.BooleanField(blank=True, default=False, null=True),
        ),
        migrations.AlterField(
            model_name="subscription",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AlterField(
            model_name="subscription",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
        ),
    ]