from rest_framework import serializers
from .models import Video


class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = [
            "id",
            "title",
            "upload_date",
            "video_file_upload",
            "video_file_transcoded",
            "share_link",
            "link_expiry_date",
            "watermark",
            "watermark_expiry_date",
            "password",
            "is_active",
            "view_count",
            "watermark_start_time",
            "watermark_end_time",
            "watermark_location",
            "thumbnail",
            "total_view_duration",
            "average_view_duration",
            "last_interaction",
            "visit_count",
            "bounce_count",
            "bounce_rate",
            "video_length",
            "view_date",
            "unique_view_count",
            "filename",
            "metadata",
        ]
