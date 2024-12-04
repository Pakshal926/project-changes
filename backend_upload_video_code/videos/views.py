import logging
import os
import tempfile
import uuid
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.files.storage import default_storage
from django.db.models import Sum
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import Video, VideoView, UniqueVideoView
from .serializers import VideoSerializer
from .utils import increment_video_view_count

logger = logging.getLogger(__name__)


class UploadViewSet(APIView):
    parser_classes = (MultiPartParser, FormParser)
    # authentication_classes = [JWTAuthentication]
    # permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        data = request.data.copy()
        data["thumbnail"] = request.FILES.get("thumbnail")
        data["share_link"] = data.get("share_link") or str(uuid.uuid4())
        data["user"] = request.user.id

        share_link = data.get("share_link")
        if Video.objects.filter(share_link=share_link).exists():
            return Response(
                {
                    "error": "The provided share link is already in use. Please choose a different one."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = VideoSerializer(data=data)
        if serializer.is_valid():
            video = serializer.save(user=request.user)

            if "video_file" in request.FILES:
                file = request.FILES["video_file"]
                unique_filename = f"videos/{video.id}_{file.name}"

                if settings.DEBUG:  # Local environment
                    try:
                        local_path = f"media/{unique_filename}"  # Adjust as needed for your local media path
                        with open(local_path, "wb+") as destination:
                            for chunk in file.chunks():
                                destination.write(chunk)
                        video.video_file_upload = local_path
                        video.filename = file.name

                        video.save()
                    except Exception as e:
                        logger.error(f"Error saving video locally: {e}")
                        return Response(
                            {"error": "Error processing video file locally"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )
                else:  # Production (S3)
                    try:
                        s3_client = boto3.client(
                            "s3",
                            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                            region_name=settings.AWS_S3_REGION_NAME,
                        )

                        s3_client.put_object(
                            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                            Key=unique_filename,
                            Body=file,
                            Metadata={"video_id": str(video.id)},
                        )

                        video.video_file_upload = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{unique_filename}"
                        video.filename = file.name

                        video.save()

                    except boto3.exceptions.S3UploadFailedError as e:
                        logger.error(f"S3 upload error: {e}")
                        return Response(
                            {"error": "Error uploading file to S3"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )
                    except Exception as e:
                        logger.error(f"Error processing video: {e}")
                        return Response(
                            {"error": "Error processing video file"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )

            return Response(
                {
                    "id": video.id,
                    "title": video.title,
                    "thumbnail": video.thumbnail.url if video.thumbnail else None,
                    "share_link": video.share_link,
                    "video_file_upload": video.video_file_upload,
                    "video_file_transcoded": video.video_file_transcoded,
                    "length": str(video.video_length) if video.video_length else None,
                    "filename": video.filename,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VideoListView(APIView):
    def get(self, request, format=None):
        videos = Video.objects.all()
        serializer = VideoSerializer(videos, many=True)
        return Response({"results": serializer.data})


class VideoUpdateView(APIView):
    def patch(self, request, pk, format=None):
        video = get_object_or_404(Video, pk=pk)
        json_data = request.data

        share_link = json_data.get("share_link")
        if share_link and share_link != video.share_link:
            if Video.objects.filter(share_link=share_link).exclude(pk=pk).exists():
                return Response(
                    {
                        "error": "The provided share link is already in use. Please choose a different one."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = VideoSerializer(video, data=json_data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DeleteVideoView(APIView):
    def delete(self, request, video_id, filename, *args, **kwargs):
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )
        single_file_key = f"videos/{video_id}_{filename}"
        folder_key_prefix = f"videos/assets/{video_id}_{filename}/"

        try:
            s3_client.delete_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=single_file_key
            )
            logger.info(f"Deleted {single_file_key} from S3.")
        except ClientError as e:
            logger.error(f"Error deleting {single_file_key}: {e}")
            return Response(
                {"error": "Error deleting video from S3"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {"message": "Video deleted successfully from S3"}, status=status.HTTP_200_OK
        )


class VideoDetailView(APIView):
    def get(self, request, pk, format=None):
        video = get_object_or_404(Video, pk=pk)

        if video.is_expired():
            return Response({"error": "Link has expired"}, status=status.HTTP_410_GONE)

        serializer = VideoSerializer(video)
        return Response(serializer.data)


class VideoShareLinkView(APIView):
    def get(self, request, share_link, format=None):
        video = get_object_or_404(Video, share_link=share_link)

        if video.is_expired():
            return Response({"error": "Link has expired"}, status=status.HTTP_410_GONE)

        increment_video_view_count(video.id)

        return Response(
            {
                "id": video.id,
                "video_file_upload": video.video_file_upload,
                "video_file_transcoded": video.video_file_transcoded,
                "link_expiry_date": video.link_expiry_date,
            }
        )


class UpdateVideoTranscodedFiles(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        video_id = request.data.get("video_id")
        transcoded_file = request.data.get("transcoded_file")
        video_length = request.data.get("video_length")

        if not video_id or not transcoded_file:
            return Response(
                {"error": "Missing video_id or transcoded_file"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            video = Video.objects.get(id=video_id)
            video.video_file_transcoded = transcoded_file
            if video_length:
                video.length = timedelta(seconds=int(video_length))
            video.save()
            serializer = VideoSerializer(video)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Video.DoesNotExist:
            return Response(
                {"error": "Video not found"}, status=status.HTTP_404_NOT_FOUND
            )


class IncrementVideoView(APIView):
    def post(self, request, video_id):
        video = get_object_or_404(Video, id=video_id)

        success = increment_video_view_count(video_id)

        if success:
            return JsonResponse(
                {
                    "id": video.id,
                    "title": video.title,
                    "view_count": video.view_count,
                    "video_url": video.video_file_upload,
                }
            )
        else:
            return JsonResponse({"error": "Failed to increment view count"}, status=500)


class AverageViewDuration(APIView):
    def post(self, request, video_id):
        video = get_object_or_404(Video, id=video_id)
        watch_time_str = request.data.get("watch_time", None)

        if watch_time_str:
            try:
                hours, minutes, seconds = map(int, watch_time_str.split(":"))
                watch_time_seconds = hours * 3600 + minutes * 60 + seconds

                video.increment_view_duration(watch_time_seconds)

                return JsonResponse(
                    {
                        "id": video.id,
                        "title": video.title,
                        "view_count": video.view_count,
                        "total_view_duration": video.total_view_duration,
                        "average_view_duration": video.average_view_duration,
                    }
                )
            except ValueError:
                return JsonResponse(
                    {"error": "Invalid watch time format. Use HH:MM:SS."}, status=400
                )
        else:
            return JsonResponse({"error": "Watch time is required."}, status=400)


class IncrementVisitView(APIView):
    def post(self, request, video_id):
        video = get_object_or_404(Video, id=video_id)
        video.increment_visit_count()
        return JsonResponse(
            {
                "id": video.id,
                "visit_count": video.visit_count,
            }
        )


class IncrementBounceView(APIView):
    def post(self, request, video_id):
        video = get_object_or_404(Video, id=video_id)
        video.increment_bounce_count()

        return JsonResponse(
            {"id": video.id, "title": video.title, "bounce_count": video.bounce_count},
            status=status.HTTP_200_OK,
        )


class VideoBounceRateView(APIView):
    def get(self, request, video_id):
        video = get_object_or_404(Video, id=video_id)
        bounce_rate = video.bounce_rate()

        return JsonResponse(
            {"id": video.id, "title": video.title, "bounce_rate": bounce_rate},
            status=status.HTTP_200_OK,
        )


class TotalViewCountView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        user = request.user
        total_views = user.get_total_views()

        return JsonResponse(
            {
                "user": user.id,
                "total_views": total_views,
            }
        )


class AverageWatchTimeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        average_watch_time = user.get_average_watch_time()

        hours, remainder = divmod(average_watch_time.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        formatted_watch_time = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

        return Response(
            {"average_watch_time": formatted_watch_time}, status=status.HTTP_200_OK
        )


class VideoViewsDateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        videos = Video.objects.filter(user=user)
        response_data = []

        for video in videos:
            views_data = (
                VideoView.objects.filter(video=video)
                .values("view_date")
                .annotate(total_views=Sum("view_count"))
                .order_by("view_date")
            )

            video_data = {
                "video_id": video.id,
                "video_title": video.title,
                "views": [
                    {
                        "date": view["view_date"].strftime("%Y-%m-%d"),
                        "total_views": view["total_views"],
                    }
                    for view in views_data
                ],
            }
            response_data.append(video_data)

        return Response({"videos": response_data})


class VideoViewsByVideoIDAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, video_id):
        user = request.user

        video = get_object_or_404(Video, id=video_id, user=user)
        views_data = (
            VideoView.objects.filter(video=video)
            .values("view_date")
            .annotate(total_views=Sum("view_count"))
            .order_by("view_date")
        )

        response_data = {
            "video_id": video.id,
            "video_title": video.title,
            "views": [
                {"date": view["view_date"], "total_views": view["total_views"]}
                for view in views_data
            ],
        }

        return Response(response_data)


class LogUniqueVideoView(APIView):
    def post(self, request):
        video_id = request.data.get("videoId")
        unique_identifier = request.data.get("unique_identifier")
        user = request.user if request.user.is_authenticated else None

        if not video_id or not unique_identifier:
            return Response(
                {"error": "Missing videoId or unique_identifier"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        video = get_object_or_404(Video, pk=video_id)
        view_date = datetime.now(timezone.utc).date()

        unique_view, created = UniqueVideoView.objects.get_or_create(
            video=video,
            view_date=view_date,
            user=user,
            unique_identifier=unique_identifier,
            defaults={},
        )

        if created:
            video.increment_unique_view_count()

        return Response(
            {"message": "Unique view logged successfully"},
            status=status.HTTP_201_CREATED,
        )


class GetTotalUniqueViewCount(APIView):
    def post(self, request):
        total_unique_views = (
            Video.objects.aggregate(total=Sum("unique_view_count"))["total"] or 0
        )

        return Response({"total_unique_views": total_unique_views}, status=200)


class GenerateSignedURLView(APIView):
    def post(self, request, *args, **kwargs):
        # Extract video metadata
        title = request.data.get("title")
        watermark = request.data.get("watermark", False)
        watermark_location = request.data.get("watermark_location")
        link_expiry_date = request.data.get("link_expiry_date")
        password = request.data.get("password")
        video_length = request.data.get("video_length")
        metadata = request.data.get("metadata", {})
        thumbnail = request.data.get("thumbnail")

        # Validate mandatory fields
        if not title:
            return Response(
                {"error": "Title is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Validate optional link_expiry_date format if provided
        if link_expiry_date:
            try:
                link_expiry_date = datetime.strptime(
                    link_expiry_date, "%Y-%m-%d %H:%M:%S"
                )
            except ValueError:
                return Response(
                    {
                        "error": "Invalid date format for link_expiry_date. It must be in YYYY-MM-DD HH:MM:SS format."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Create video record in the database
        try:
            video = Video.objects.create(
                title=title,
                watermark=watermark or False,
                watermark_location=watermark_location or None,
                link_expiry_date=link_expiry_date or None,
                password=password or None,
                video_length=video_length or None,
                metadata=metadata or {},
                thumbnail=thumbnail or None,
            )
        except Exception as e:
            logging.error(f"Database error: {e}")
            return Response(
                {"error": f"Failed to create video record: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Generate the video ID based on the auto-incremented primary key
        video_id = video.id

        # Generate the file path
        file_path = f"videos/{video_id}.mp4"

        # Update the file path in the video record
        try:
            video.video_file_upload = file_path
            video.save()
        except Exception as e:
            logging.error(f"Database error while saving file path: {e}")
            return Response(
                {"error": f"Failed to update video file path: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Generate the signed URL for S3
        try:
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME,
            )
            upload_url = s3_client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                    "Key": file_path,
                    "ContentType": "video/mp4",
                    "ACL": "public-read",
                },
                ExpiresIn=3600,
            )
        except Exception as e:
            logging.error(f"S3 error: {e}")
            return Response(
                {"error": f"Failed to generate signed URL: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "video_id": video_id,
                "upload_url": upload_url,
                "file_path": file_path,
            },
            status=status.HTTP_201_CREATED,
        )


class UpdateUploadStatusView(APIView):
    def post(self, request, *args, **kwargs):
        # Extract the video ID and status from the request
        video_id = request.data.get("video_id")
        status_update = request.data.get("status")

        # Validate required fields
        if not video_id or not status_update:
            return Response(
                {"error": "Video ID and status are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate the status value
        valid_statuses = ["PENDING", "UPLOADED", "TRANSCODING", "TRANSCODED"]
        if status_update not in valid_statuses:
            return Response(
                {"error": "Invalid status."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Fetch the video object
        try:
            video = Video.objects.get(id=video_id)
        except Video.DoesNotExist:
            return Response(
                {"error": "Video not found."}, status=status.HTTP_404_NOT_FOUND
            )

        # Update the video status
        previous_status = video.upload_status
        video.upload_status = status_update
        video.save()

        # Log the status update
        logging.info(
            f"Video {video_id} status updated from {previous_status} to {status_update}"
        )

        # Publish event or take specific actions based on the new status
        if status_update == "UPLOADED":
            logging.info(
                f"Video {video_id} has been uploaded. Proceeding with AWS workflows."
            )
            # (Optional) Publish event for transcoding (e.g., via SQS or SNS)
        elif status_update == "TRANSCODED":
            logging.info(f"Video {video_id} transcoding complete. Ready for playback.")
            # Handle post-transcoding workflows if needed

        return Response(
            {"message": f"Video {video_id} status updated to {status_update}"},
            status=status.HTTP_200_OK,
        )
