from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Sum
from django.utils import timezone


class Video(models.Model):
    WATERMARK_LOCATIONS = [
        ("top_left", "Top Left"),
        ("top_right", "Top Right"),
        ("bottom_left", "Bottom Left"),
        ("bottom_right", "Bottom Right"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL, related_name="videos"
    )
    title = models.CharField(max_length=100, blank=True, null=True)
    upload_date = models.DateTimeField(auto_now_add=True)
    video_file_upload = models.URLField(blank=True, null=True)
    video_file_transcoded = models.URLField(blank=True, null=True)
    share_link = models.CharField(max_length=225, blank=True, null=True, unique=True)
    link_expiry_date = models.DateTimeField(blank=True, null=True)
    watermark = models.BooleanField(default=False)
    watermark_location = models.CharField(
        max_length=20, choices=WATERMARK_LOCATIONS, blank=True, null=True
    )
    watermark_start_time = models.DurationField(blank=True, null=True)
    watermark_end_time = models.DurationField(blank=True, null=True)
    watermark_expiry_date = models.DateTimeField(blank=True, null=True)
    password = models.CharField(max_length=128, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    view_count = models.PositiveIntegerField(default=0)
    total_view_duration = models.DurationField(default=timezone.timedelta(0))
    average_view_duration = models.DurationField(blank=True, default=None, null=True)
    bounce_count = models.PositiveIntegerField(default=0)
    last_interaction = models.DateTimeField(blank=True, null=True)
    visit_count = models.PositiveIntegerField(default=0)
    bounce_rate = models.FloatField(default=0.0)
    video_length = models.DurationField(blank=True, null=True)
    thumbnail = models.ImageField(upload_to="thumbnails/", blank=True, null=True)
    view_date = models.DateField(auto_now_add=True, null=True)
    unique_view_count = models.PositiveIntegerField(default=0)
    filename = models.CharField(max_length=255, blank=True, null=True)
    metadata = models.JSONField(blank=True, null=True)

    def __str__(self):
        return self.title if self.title else "Untitled Video"

    def save(self, *args, **kwargs):
        self.bounce_rate = self.calculate_bounce_rate()
        super().save(*args, **kwargs)

    def is_expired(self):
        if self.link_expiry_date:
            if timezone.is_naive(self.link_expiry_date):
                self.link_expiry_date = timezone.make_aware(self.link_expiry_date)
                self.save(update_fields=["link_expiry_date"])
            expired = timezone.now() > self.link_expiry_date
            if expired and self.is_active:
                self.is_active = False
                self.save(update_fields=["is_active"])
            return expired
        return False

    def check_password(self, input_password):
        return self.password == input_password

    def update_average_view_duration(self):
        if self.view_count > 0:
            self.average_view_duration = self.total_view_duration / self.view_count

            total_seconds = int(self.average_view_duration.total_seconds())
            self.average_view_duration = timezone.timedelta(seconds=total_seconds)
        else:
            self.average_view_duration = timezone.timedelta(0)

        self.save(update_fields=["average_view_duration"])

    def increment_view_duration(self, watch_time_seconds):
        self.total_view_duration += timezone.timedelta(seconds=watch_time_seconds)
        self.update_average_view_duration()
        self.save(update_fields=["total_view_duration", "average_view_duration"])

    def calculate_bounce_rate(self):
        if self.visit_count > 0:
            return round((self.bounce_count / self.visit_count) * 100, 2)
        return 0.0

    def increment_visit_count(self):
        self.visit_count += 1
        self.save(update_fields=["visit_count"])

    def increment_bounce_count(self):
        if self.visit_count > 0 and self.bounce_count < self.visit_count:
            self.bounce_count += 1
            self.save(update_fields=["bounce_count"])

    def get_views_for_date_range(self, start_date, end_date):
        return (
            self.views.filter(view_date__range=[start_date, end_date]).aggregate(
                total_views=Sum("view_count")
            )["total_views"]
            or 0
        )

    @staticmethod
    def get_total_views_for_user_on_date(user, specific_date):
        total_views = (
            VideoView.objects.filter(
                video__user=user, view_date=specific_date
            ).aggregate(total_views=Sum("view_count"))["total_views"]
            or 0
        )

        return total_views

    @staticmethod
    def get_total_views_for_user_in_date_range(user, start_date, end_date):
        return (
            VideoView.objects.filter(
                video__user=user, view_date__range=[start_date, end_date]
            ).aggregate(total_views=Sum("view_count"))["total_views"]
            or 0
        )

    def increment_unique_view_count(self):
        self.unique_view_count += 1
        self.save(update_fields=["unique_view_count"])


class VideoView(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name="views")
    view_date = models.DateField()
    view_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("video", "view_date")

    def __str__(self):
        return f"{self.video.title} - {self.view_date}: {self.view_count} views"


class UniqueVideoView(models.Model):
    video = models.ForeignKey(
        Video, on_delete=models.CASCADE, related_name="unique_views"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE
    )
    unique_identifier = models.CharField(max_length=255, blank=True, null=True)
    view_date = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = ("video", "user", "unique_identifier", "view_date")

    def __str__(self):
        if self.user:
            return f"Unique view by {self.user} on {self.view_date}"
        else:
            return f"Unique view with identifier {self.unique_identifier} on {self.view_date}"
