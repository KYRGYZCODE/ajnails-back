from rest_framework import serializers
from .models import Service, Lead, Client
from users.serializers import UserGet


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = '__all__'


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = '__all__'


class LeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = '__all__'


    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['service'] = ServiceSerializer(instance.service).data
        representation['master'] = UserGet(instance.master).data
        representation['client'] = ClientSerializer(instance.client).data if instance.client else None
        return representation


class BusySlotSerializer(serializers.Serializer):
    date_time = serializers.DateTimeField()
    master_id = serializers.UUIDField()
