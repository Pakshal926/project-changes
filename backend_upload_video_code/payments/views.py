import datetime
import logging
import secrets
import stripe
from accounts.models import User
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Subscription

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)


class CreateCheckoutSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            price_id = request.data.get("price_id")
            if not price_id:
                return Response(
                    {"error": "Price ID is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Generate secure tokens
            success_token = secrets.token_urlsafe(32)
            cancel_token = secrets.token_urlsafe(32)

            # Save tokens in the user's session or a secure cache
            request.session["success_token"] = success_token
            request.session["cancel_token"] = cancel_token

            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                mode="subscription",
                line_items=[{"price": price_id, "quantity": 1}],
                success_url=(
                    f"http://localhost:3000/payment_checkout/success?token={success_token}"
                    if settings.DEBUG
                    else f"https://platform.sealsafe.io/payment_checkout/success?token={success_token}"
                ),
                cancel_url=(
                    f"http://localhost:3000/payment_checkout/cancel?token={cancel_token}"
                    if settings.DEBUG
                    else f"https://platform.sealsafe.io/payment_checkout/cancel?token={cancel_token}"
                ),
                metadata={"user_id": str(request.user.id)},
            )
            return Response({"id": session.id}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error creating Stripe session: {e}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ValidateTokenView(APIView):
    def get(self, request):
        token = request.query_params.get("token")
        type_ = request.query_params.get("type")

        if not token or type_ not in ["success", "cancel"]:
            return Response(
                {"error": "Invalid token or type."}, status=status.HTTP_400_BAD_REQUEST
            )

        session_token = request.session.get(f"{type_}_token")

        if session_token == token:
            # Optionally clear token after validation
            del request.session[f"{type_}_token"]
            return Response({"valid": True}, status=status.HTTP_200_OK)

        return Response({"valid": False}, status=status.HTTP_403_FORBIDDEN)


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(View):
    def post(self, request, *args, **kwargs):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            logger.error(f"Webhook signature verification error: {e}")
            return HttpResponse(status=400)

        event_type = event["type"]
        handler_mapping = {
            "checkout.session.completed": self.handle_subscription_success,
            "invoice.payment_succeeded": self.handle_payment_succeeded,
            "invoice.payment_failed": self.handle_payment_failed,
            "customer.subscription.deleted": self.handle_subscription_canceled,
            "customer.subscription.updated": self.handle_subscription_updated,
        }

        try:
            handler = handler_mapping.get(event_type)
            if handler:
                handler(event["data"]["object"])
        except Exception as e:
            logger.error(f"Error handling event {event_type}: {e}")
            return HttpResponse(status=500)

        return HttpResponse(status=200)

    def handle_subscription_success(self, session):
        stripe_customer_id = session.get("customer")
        stripe_subscription_id = session.get("subscription")
        stripe_checkout_session_id = session.get("id")
        user_id = session.get("metadata", {}).get(
            "user_id"
        )  # Extract user_id as string

        if not stripe_subscription_id or not stripe_customer_id:
            logger.error("Subscription or customer ID missing in session data.")
            return

        try:
            stripe_subscription = stripe.Subscription.retrieve(stripe_subscription_id)
            price_id = stripe_subscription.plan.id
        except stripe.error.StripeError as e:
            logger.error(f"Stripe API error: {e}")
            return

        if user_id:
            try:
                user_id = int(user_id)  # Convert user_id to an integer
                user = User.objects.get(id=user_id)
            except (ValueError, User.DoesNotExist):
                logger.warning(f"No user found for user ID {user_id}")
                return

        try:
            with transaction.atomic():
                subscription, created = Subscription.objects.get_or_create(
                    stripe_checkout_session_id=stripe_checkout_session_id,  # Match or create by session ID
                    defaults={
                        "user": user,  # Set the user
                        "stripe_customer_id": stripe_customer_id,
                        "stripe_subscription_id": stripe_subscription_id,
                        "stripe_price_id": price_id,
                        "subscription_status": stripe_subscription.status,
                        "current_period_start": timezone.make_aware(
                            datetime.fromtimestamp(
                                stripe_subscription.current_period_start
                            )
                        ),
                        "current_period_end": timezone.make_aware(
                            datetime.fromtimestamp(
                                stripe_subscription.current_period_end
                            )
                        ),
                        "cancel_at_period_end": stripe_subscription.cancel_at_period_end,
                        "subscription_tier": Subscription.get_tier_from_price_id(
                            price_id
                        ),
                    },
                )

                if not created:
                    subscription.update_status_from_stripe(stripe_subscription)

                subscription.save()
                logger.info(f"Subscription successfully saved for user {user_id}")
        except Exception as e:
            logger.error(f"Error handling subscription success: {e}")

    def handle_payment_succeeded(self, invoice):
        stripe_subscription_id = invoice.get("subscription")
        if stripe_subscription_id:
            try:
                stripe_subscription = stripe.Subscription.retrieve(
                    stripe_subscription_id
                )
                user = User.objects.filter(
                    subscription__stripe_subscription_id=stripe_subscription_id
                ).first()
                if user:
                    user.subscription.update_status_from_stripe(stripe_subscription)
                    user.subscription.save()
                    logger.info(
                        f"Subscription updated in database for user {user.id} due to payment success"
                    )
                else:
                    logger.error(
                        f"No user found for subscription ID {stripe_subscription_id}"
                    )
            except Exception as e:
                logger.error(
                    f"Error updating subscription status on payment success: {e}"
                )

    def handle_payment_failed(self, invoice):
        stripe_subscription_id = invoice.get("subscription")
        if stripe_subscription_id:
            try:
                user = User.objects.filter(
                    subscription__stripe_subscription_id=stripe_subscription_id
                ).first()
                if user:
                    user.subscription.subscription_status = "incomplete"
                    user.subscription.save()
                    logger.info(
                        f"Subscription set to 'incomplete' for user {user.id} due to payment failure"
                    )
            except Exception as e:
                logger.error(
                    f"Error handling payment failure for subscription {stripe_subscription_id}: {e}"
                )

    def handle_subscription_updated(self, subscription):
        stripe_subscription_id = subscription.get("id")
        try:
            user = User.objects.filter(
                subscription__stripe_subscription_id=stripe_subscription_id
            ).first()
            if user:
                stripe_subscription = stripe.Subscription.retrieve(
                    stripe_subscription_id
                )
                user.subscription.update_status_from_stripe(stripe_subscription)
        except Exception as e:
            logger.error(
                f"Error updating subscription for {stripe_subscription_id}: {e}"
            )

    def handle_subscription_canceled(self, subscription):
        stripe_subscription_id = subscription.get("id")
        try:
            user = User.objects.filter(
                subscription__stripe_subscription_id=stripe_subscription_id
            ).first()
            if user:
                user.subscription.subscription_status = "canceled"
                user.subscription.current_period_end = timezone.now()
                user.subscription.save()
                logger.info(f"Subscription canceled for user {user.id}")
        except Exception as e:
            logger.error(
                f"Error canceling subscription for {stripe_subscription_id}: {e}"
            )


@method_decorator(login_required, name="dispatch")
class SubscriptionStatusView(View):
    def get(self, request):
        try:
            subscription = request.user.subscription
            price = stripe.Price.retrieve(subscription.stripe_price_id)
            data = {
                "subscription_plan": subscription.subscription_tier,
                "subscription_date": subscription.created_at,
                "subscription_status": subscription.transaction_status,
                "price": {
                    "amount": price.unit_amount / 100,
                    "currency": price.currency.upper(),
                },
            }
            return JsonResponse(data)
        except Subscription.DoesNotExist:
            return JsonResponse({"error": "No active subscription"}, status=404)


class RetrieveSessionDetailsView(View):
    def post(self, request, *args, **kwargs):
        try:
            session_id = request.POST.get("session_id")
            if not session_id:
                return JsonResponse({"error": "Session ID is required"}, status=400)

            session = stripe.checkout.Session.retrieve(
                session_id, expand=["line_items"]
            )
            stripe_subscription_id = session.get("subscription")
            stripe_customer_id = session.get("customer")

            if not stripe_subscription_id or not stripe_customer_id:
                return JsonResponse({"error": "Invalid session data"}, status=400)

            user_id = session.get("metadata", {}).get("user_id")
            if not user_id:
                return JsonResponse(
                    {"error": "User ID missing in session metadata"}, status=400
                )

            user = User.objects.get(id=user_id)

            price_id = session.line_items.data[0].price.id

            subscription, created = Subscription.objects.get_or_create(
                user=user,
                defaults={
                    "stripe_customer_id": stripe_customer_id,
                    "stripe_subscription_id": stripe_subscription_id,
                    "stripe_price_id": price_id,
                    "subscription_status": session.status,
                    "current_period_start": timezone.now(),
                    "current_period_end": timezone.now(),
                },
            )

            if not created:
                try:
                    stripe_subscription = stripe.Subscription.retrieve(
                        stripe_subscription_id
                    )
                    subscription.update_status_from_stripe(stripe_subscription)
                except stripe.error.InvalidRequestError as e:
                    logger.error(f"Invalid subscription ID: {e}")
                    return JsonResponse(
                        {"error": "Invalid subscription ID"}, status=400
                    )
                except stripe.error.APIConnectionError as e:
                    logger.error(f"Stripe API connection error: {e}")
                    return JsonResponse(
                        {"error": "Network error, please try again later"}, status=503
                    )
                except stripe.error.StripeError as e:
                    logger.error(f"Stripe API error: {e}")
                    return JsonResponse(
                        {
                            "error": "An error occurred with Stripe, please try again later"
                        },
                        status=500,
                    )
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
                    return JsonResponse(
                        {"error": "An unexpected error occurred"}, status=500
                    )
            return JsonResponse(
                {"status": "success", "subscription_id": subscription.id}
            )

        except User.DoesNotExist:
            return JsonResponse({"error": "User not found"}, status=404)
        except Exception as e:
            logger.error(f"Error in RetrieveSessionDetailsView: {e}")
            return JsonResponse({"error": str(e)}, status=500)
