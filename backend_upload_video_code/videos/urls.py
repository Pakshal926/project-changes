from django.urls import path
from .views import (
    AverageViewDuration,
    AverageWatchTimeView,
    DeleteVideoView,
    GenerateSignedURLView,
    GetTotalUniqueViewCount,
    IncrementBounceView,
    IncrementVideoView,
    IncrementVisitView,
    LogUniqueVideoView,
    TotalViewCountView,
    UpdateUploadStatusView,
    UpdateVideoTranscodedFiles,
    UploadViewSet,
    VideoBounceRateView,
    VideoDetailView,
    VideoListView,
    VideoShareLinkView,
    VideoUpdateView,
    VideoViewsByVideoIDAPI,
    VideoViewsDateAPI,
)

urlpatterns = [
    path("upload/", UploadViewSet.as_view(), name="upload"),
    path("list/", VideoListView.as_view(), name="video-list"),
    path("update/<int:pk>/", VideoUpdateView.as_view(), name="video-update"),
    path("detail/<int:pk>/", VideoDetailView.as_view(), name="video-detail"),
    path(
        "delete/<int:video_id>/<str:filename>/",
        DeleteVideoView.as_view(),
        name="delete-video",
    ),
    path(
        "share/<str:share_link>/", VideoShareLinkView.as_view(), name="video-share-link"
    ),
    path(
        "update-transcoded-files-location/",
        UpdateVideoTranscodedFiles.as_view(),
        name="update-transcoded-files-location",
    ),
    path(
        "increment-view/<int:video_id>/",
        IncrementVideoView.as_view(),
        name="increment_video_view",
    ),
    path(
        "average-view-duration/<int:video_id>/",
        AverageViewDuration.as_view(),
        name="average-view-duration",
    ),
    path(
        "increment-visit/<int:video_id>/",
        IncrementVisitView.as_view(),
        name="increment-visit",
    ),
    path(
        "increment-bounce/<int:video_id>/",
        IncrementBounceView.as_view(),
        name="increment-bounce",
    ),
    path(
        "bounce-rate/<int:video_id>/",
        VideoBounceRateView.as_view(),
        name="video-bounce-rate",
    ),
    path("total-view-count/", TotalViewCountView.as_view(), name="total-view-count"),
    path(
        "average-watch-time/", AverageWatchTimeView.as_view(), name="average-watch-time"
    ),
    path("video-views-date/", VideoViewsDateAPI.as_view(), name="video-views-date"),
    path(
        "video-views-date/<int:video_id>/",
        VideoViewsByVideoIDAPI.as_view(),
        name="video-views-date-id",
    ),
    path(
        "log_unique_video_view/",
        LogUniqueVideoView.as_view(),
        name="log-unique-video-view",
    ),
    path(
        "total_unique_video_view/",
        GetTotalUniqueViewCount.as_view(),
        name="total_unique_video_view",
    ),
    path(
        "generate-signed-url/",
        GenerateSignedURLView.as_view(),
        name="generate-signed-url",
    ),
    path(
        "update-upload-status/",
        UpdateUploadStatusView.as_view(),
        name="update-upload-status",
    ),
]
