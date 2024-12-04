import requests
from rest_framework.reverse import reverse
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenViewBase
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from django.contrib.auth import authenticate, get_user_model
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
import logging

from .serializers import UserSerializer, PasswordResetSerializer
from mailers.models import VerificationCode

logging.basicConfig(level=logging.DEBUG)

User = get_user_model()


class SignUpView(APIView):
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            response_data = {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,  
                'last_name': user.last_name, 
                'refresh': str(refresh),
                'access': str(refresh.access_token)
            }

            headers = {
                'Authorization': f'Bearer {response_data["access"]}'
            }

            verification_url = request.build_absolute_uri(reverse('send_verification_email'))
            response = requests.post(verification_url, headers=headers)

            if response.status_code != 200:
                return Response({'error': 'Failed to send verification email'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response(response_data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserLoginView(APIView):
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        user = authenticate(request, email=email, password=password)
        if user:
            refresh = RefreshToken.for_user(user)
            serializer = UserSerializer(user)
            response_data = {
                'user': serializer.data,
                'refresh': str(refresh),
                'access': str(refresh.access_token)
            }   
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)


class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PasswordResetView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            verification_code = serializer.validated_data['verification_code']
            new_password = serializer.validated_data['new_password']

            user = get_object_or_404(User, email=email)
            verification_code_obj = get_object_or_404(VerificationCode, email=email)

            if verification_code_obj.code == verification_code and not verification_code_obj.is_expired():
                if user.is_verified:
                    user.set_password(new_password)
                    user.save()
                    return Response({'message': 'Password updated successfully'}, status=status.HTTP_200_OK)
                else:
                    return Response({'error': 'User is not verified, please verify your account'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({'error': 'Invalid or expired verification code'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SendVerificationResetPassword(APIView):
    def post(self, request):
        email = request.data.get('email')
        verification = VerificationCode.objects.get(email=email)
        verification.reset()
        verification.save() 

        return Response({'message': 'Verification code generated successfully'}, status=status.HTTP_200_OK)


class CheckPasswordResetVerification(APIView):
    def post(self, request):
        email = request.data.get('email')
        code = request.data.get('code')

        try:
            verification_code = VerificationCode.objects.get(email=email)
            if verification_code.code == code:
                user = User.objects.get(email=email)

                refresh = RefreshToken.for_user(user)
                response_data = {
                    'message': 'Verification Code Matches',
                    'refresh': str(refresh),
                    'access': str(refresh.access_token)
                }

                return Response(response_data, status=status.HTTP_200_OK)
            else:
                return Response({'message': 'Verification Code does not Match'}, status=status.HTTP_400_BAD_REQUEST)
        except VerificationCode.DoesNotExist:
            return Response({'message': 'Invalid request'}, status=status.HTTP_400_BAD_REQUEST)

class TokenRefreshView(TokenViewBase):
    serializer_class = TokenRefreshSerializer
