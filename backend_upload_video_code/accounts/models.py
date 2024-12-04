from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Avg, F, ExpressionWrapper, DurationField
from django.utils import timezone


class User(AbstractUser):
    email = models.EmailField(unique=True)
    is_verified = models.BooleanField(default=False)
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email

    def get_total_views(self):
        return self.videos.aggregate(total_views=models.Sum('view_count'))['total_views'] or 0

    def get_average_watch_time(self):
        avg_watch_time = self.videos.aggregate(
            average_watch_time=Avg(
                ExpressionWrapper(F('average_view_duration'), output_field=DurationField())
            )
        )['average_watch_time']
        
        return avg_watch_time or timezone.timedelta(0)
