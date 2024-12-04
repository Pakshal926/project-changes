from datetime import datetime, timedelta
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken

UserModel = get_user_model()

class UserTestCase(APITestCase):
    def setUp(self):
        self.user = UserModel.objects.create_user(
            username='testuser', 
            email='test@example.com', 
            password='testpassword'
        )
        
        self.login_url = reverse('user_login')
        self.refresh_token_url = reverse('refresh_token')
        
        response = self.client.post(self.login_url, {
            'email': 'test@example.com',
            'password': 'testpassword'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.refresh_token = response.data['refresh']
        self.access_token = response.data['access']

    def test_login(self):
        url = self.login_url
        data = {'email': 'test@example.com', 'password': 'testpassword'}
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('refresh', response.data)
        self.assertIn('access', response.data)

    def test_login_invalid_credentials(self):
        url = self.login_url
        data = {'email': 'invalid@example.com', 'password': 'invalidpassword'}
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)

    def test_user_detail_authenticated(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        url = reverse('user_detail')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.user.id)
        self.assertEqual(response.data['username'], self.user.username)
        self.assertEqual(response.data['email'], self.user.email)

    def test_user_detail_unauthenticated(self):
        url = reverse('user_detail') 
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh_success(self):
        """Test refreshing token with a valid refresh token."""
        response = self.client.post(self.refresh_token_url, {
            'refresh': self.refresh_token
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        
        new_access_token = response.data['access']
        new_refresh_token = response.data['refresh']
        
        self.assertNotEqual(self.access_token, new_access_token)
        self.assertNotEqual(self.refresh_token, new_refresh_token)
        self.assertIsNotNone(new_access_token)
        self.assertIsNotNone(new_refresh_token)

    def test_token_refresh_invalid_token(self):
        """Test refreshing token with an invalid refresh token."""
        response = self.client.post(self.refresh_token_url, {
            'refresh': 'invalid_refresh_token'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('detail', response.data)
