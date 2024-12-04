from datetime import datetime
from django.conf import settings
from django.db import models
from django.utils import timezone


class Subscription(models.Model):
    TIER_CHOICES = [
        ("standard", "Standard"),
        ("advanced", "Advanced"),
    ]
    SUBSCRIPTION_STATUS = [("success", "Success"), ("cancelled", "Cancelled")]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="subscription",
    )
    stripe_customer_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_subscription_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_price_id = models.CharField(max_length=255, null=True, blank=True)
    subscription_status = models.CharField(max_length=50, null=True, blank=True)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(null=True, blank=True, default=False)
    created_at = models.DateTimeField(null=True, blank=True, auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True, auto_now=True)
    subscription_tier = models.CharField(
        max_length=20, choices=TIER_CHOICES, null=True, blank=True
    )
    stripe_checkout_session_id = models.CharField(max_length=255, null=True, blank=True)
    transaction_status = models.CharField(
        max_length=20, choices=SUBSCRIPTION_STATUS, null=True, blank=True
    )

    def __str__(self):
        return (
            f"{self.user}'s Subscription ({self.subscription_status})"
            if self.user
            else "Subscription (No User)"
        )

    def update_status_from_stripe(self, stripe_subscription):
        self.stripe_subscription_id = stripe_subscription.id
        self.subscription_status = stripe_subscription.status
        self.current_period_start = timezone.make_aware(
            datetime.fromtimestamp(stripe_subscription.current_period_start)
        )
        self.current_period_end = timezone.make_aware(
            datetime.fromtimestamp(stripe_subscription.current_period_end)
        )
        self.cancel_at_period_end = stripe_subscription.cancel_at_period_end
        self.subscription_tier = Subscription.get_tier_from_price_id(
            stripe_subscription.plan.id
        )
        self.save()

    @staticmethod
    def get_tier_from_price_id(price_id):
        tier_map = {
            "price_standard_tier_id": "standard",
            "price_advanced_tier_id": "advanced",
        }
        return tier_map.get(price_id, "standard")

    @classmethod
    def create_from_stripe_session(cls, session_data):
        subscription = (
            cls.objects.filter(stripe_checkout_session_id=session_data.id).first()
            or cls()
        )

        subscription.stripe_checkout_session_id = session_data.id
        subscription.stripe_customer_id = session_data.customer
        if session_data.client_reference_id:
            try:
                user = settings.AUTH_USER_MODEL.objects.get(
                    id=session_data.client_reference_id
                )
                subscription.user = user
            except settings.AUTH_USER_MODEL.DoesNotExist:
                pass

        subscription.save()
        return subscription
