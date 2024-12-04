from django.urls import path
from .views import (
    CreateCheckoutSessionView,
    StripeWebhookView,
    SubscriptionStatusView,
    ValidateTokenView,
)

urlpatterns = [
    path(
        "create-checkout-session/",
        CreateCheckoutSessionView.as_view(),
        name="create_checkout_session",
    ),
    path("stripe-webhook/", StripeWebhookView.as_view(), name="stripe_webhook"),
    path(
        "subscription-status/",
        SubscriptionStatusView.as_view(),
        name="subscription_status",
    ),
    path("validate-token/", ValidateTokenView.as_view(), name="validate-token"),
]
