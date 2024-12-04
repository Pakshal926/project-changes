import json
import os
from accounts.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Video


class VideoAPITestCase(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + self.access_token)

        self.video_file_path = os.path.join(os.path.dirname(__file__), "test_video.mp4")
        with open(self.video_file_path, "wb") as f:
            f.write(os.urandom(1024 * 1024))

    def tearDown(self):
        if os.path.exists(self.video_file_path):
            os.remove(self.video_file_path)

    def test_list_videos(self):
        videos = [
            Video.objects.create(title=f"Test Video {i}", user=self.user)
            for i in range(1, 4)
        ]

        response = self.client.get(reverse("video-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("results" in response.data)
        self.assertTrue(isinstance(response.data["results"], list))
        self.assertEqual(len(response.data["results"]), len(videos))

    def test_update_video(self):
        video = Video.objects.create(title="New Title", user=self.user)
        url = reverse("video-update", kwargs={"pk": video.pk})
        data = {"title": "New Title"}

        response = self.client.patch(url, data, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "New Title")

    def test_partial_update_video(self):
        video = Video.objects.create(title="Old Title", user=self.user)
        url = reverse("video-update", kwargs={"pk": video.pk})
        data = {"title": "Updated Title"}

        response = self.client.patch(url, data, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Updated Title")

    def test_delete_video(self):
        video = Video.objects.create(title="Test Video", user=self.user)
        url = reverse("video-delete", kwargs={"pk": video.pk})

        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Video.objects.filter(pk=video.pk).exists())

    def test_retrieve_video_details(self):
        video = Video.objects.create(title="Test Video", user=self.user)
        url = reverse("video-detail", kwargs={"pk": video.pk})

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Test Video")

    def test_retrieve_video_with_invalid_id(self):
        url = reverse("video-detail", kwargs={"pk": 999})

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_video_by_share_link(self):
        video = Video.objects.create(
            title="Test Video", share_link="test_share_link", user=self.user
        )
        url = reverse("video-share-link", kwargs={"share_link": video.share_link})

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], video.id)

    def test_delete_video_with_invalid_id(self):
        url = reverse("video-delete", kwargs={"pk": 999})

        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


def test_increment_video_view_count(self):
    video = Video.objects.create(title="Test Video", user=self.user)

    self.assertEqual(video.view_count, 0)

    url = reverse("increment_video_view", kwargs={"video_id": video.id})
    response = self.client.get(url)

    response_data = json.loads(response.content)

    self.assertEqual(response.status_code, status.HTTP_200_OK)
    self.assertEqual(response_data["view_count"], 1)
    self.assertEqual(response_data["id"], video.id)
    self.assertEqual(response_data["title"], video.title)


def test_upload_video(self):
    url = reverse("upload")
    with open(self.video_file_path, "rb") as f:
        response = self.client.post(
            url, {"video": f, "title": "Uploaded Video"}, format="multipart"
        )

    self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    self.assertEqual(response.data["title"], "Uploaded Video")
    self.assertTrue(Video.objects.filter(title="Uploaded Video").exists())


def test_average_watch_time(self):
    url = reverse("average-watch-time")
    response = self.client.get(url)

    self.assertEqual(response.status_code, status.HTTP_200_OK)
    self.assertIn("average_watch_time", response.data)


def test_total_unique_video_view(self):
    url = reverse("total_unique_video_view")
    response = self.client.get(url)

    self.assertEqual(response.status_code, status.HTTP_200_OK)
    self.assertIn("total_unique_views", response.data)


def test_video_bounce_rate(self):
    video = Video.objects.create(title="Test Video", user=self.user)
    url = reverse("video-bounce-rate", kwargs={"video_id": video.id})
    response = self.client.get(url)

    self.assertEqual(response.status_code, status.HTTP_200_OK)
    self.assertIn("bounce_rate", response.data)


def test_increment_visit(self):
    video = Video.objects.create(title="Test Video", user=self.user)
    url = reverse("increment-visit", kwargs={"video_id": video.id})

    response = self.client.get(url)
    self.assertEqual(response.status_code, status.HTTP_200_OK)
