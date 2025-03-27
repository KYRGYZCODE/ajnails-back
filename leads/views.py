from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils.timezone import now
from django.db.models import Q
from django.contrib.auth import get_user_model
from .models import Service, Lead, Appointment
from .serializers import ServiceSerializer,  LeadSerializer, AppointmentSerializer
from users.serializers import UserGet

User = get_user_model()

class ServiceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    permission_classes = [permissions.AllowAny]

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.filter(is_employee=True)
    serializer_class = UserGet
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        service_id = self.request.query_params.get("service")
        date_time = self.request.query_params.get("date_time")
        
        queryset = self.queryset
        
        if service_id:
            queryset = queryset.filter(services__id=service_id)
        
        if date_time:
            busy_masters = Appointment.objects.filter(date_time=date_time).values_list("master", flat=True)
            queryset = queryset.exclude(id__in=busy_masters)
        
        return queryset

class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def busy_slots(self, request):
        busy_leads = Lead.objects.values("date_time", "master_id")
        busy_appointments = Appointment.objects.values("date_time", "master_id")
        
        busy_slots = list(busy_leads) + list(busy_appointments)
        return Response(busy_slots)

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

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def convert_to_appointment(self, request, pk=None):
        lead = self.get_object()
        user = request.user
        
        if user.role != "manager":
            return Response({"error": "Only managers can convert leads."}, status=status.HTTP_403_FORBIDDEN)

        if lead.prepayment <= 0:
            return Response({"error": "Lead must have prepayment to be converted."}, status=status.HTTP_400_BAD_REQUEST)

        appointment = Appointment.objects.create(
            client_name=lead.client_name,
            client_phone=lead.phone,
            master=lead.master,
            service=lead.service,
            date_time=lead.date_time,
        )
        
        lead.delete()
        return Response(AppointmentSerializer(appointment).data, status=status.HTTP_201_CREATED)
