from django.utils import timezone
from .models import Video, VideoView


def increment_video_view_count(video_id):
    try:
        video = Video.objects.get(pk=video_id)
        video.view_count += 1
        video.save()
        today = timezone.now().date()

        video_view, created = VideoView.objects.get_or_create(
            video=video, view_date=today
        )
        video_view.view_count += 1
        video_view.save()

        return True
    except Video.DoesNotExist:
        return False
    except Exception as e:
        print(f"Error incrementing view count: {e}")
        return False
