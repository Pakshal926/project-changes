from django.urls import path
from .views import UserLoginView, UserDetailView, SignUpView, PasswordResetView, CheckPasswordResetVerification, SendVerificationResetPassword, TokenRefreshView

urlpatterns = [
    path('register/', SignUpView.as_view(), name='register_user'), 
    path('login/', UserLoginView.as_view(), name='user_login'),
    path('me/', UserDetailView.as_view(), name='user_detail'),
    path('reset_password/', PasswordResetView.as_view(), name='user_reset_password'),
    path('check-password-verification-code/', CheckPasswordResetVerification.as_view(), name='check-password-verification-code'),
    path('send-verification-code-reset-password/', SendVerificationResetPassword.as_view(), name='send-verification-code-reset-password'),
    path('refresh-token/', TokenRefreshView.as_view(), name='refresh_token'),
]
