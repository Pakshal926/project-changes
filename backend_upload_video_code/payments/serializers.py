from rest_framework import serializers
from .models import Subscription


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = "__all__"

    def create(self, validated_data):
        user = validated_data.get("user", None)
        subscription = Subscription.objects.create(**validated_data)
        if not user:
            pass
        return subscription
