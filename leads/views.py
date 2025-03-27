from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils.timezone import now
from django.db.models import Q
from django.contrib.auth import get_user_model
from .models import Client, Service, Lead
from .serializers import ClientSerializer, ServiceSerializer,  LeadSerializer
from users.serializers import UserGet

User = get_user_model()

class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer


class ServiceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    permission_classes = [permissions.AllowAny]


class LeadViewSet(viewsets.ModelViewSet):
    queryset = Lead.objects.all()
    serializer_class = LeadSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        data = request.data
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def busy_slots(self, request):
        busy_leads = Lead.objects.values("date_time", "master_id")
        
        return Response(busy_leads)
