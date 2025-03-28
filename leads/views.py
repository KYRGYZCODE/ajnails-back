from rest_framework.exceptions import ValidationError as DRFValidationError
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
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


class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    permission_classes = [permissions.AllowAny]


class LeadViewSet(viewsets.ModelViewSet):
    queryset = Lead.objects.all()
    serializer_class = LeadSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
        except DjangoValidationError as e:
            raise DRFValidationError(e.messages)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def busy_slots(self, request):
        busy_leads = Lead.objects.values("date_time", "master_id")
        
        return Response(busy_leads)
        
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'date', openapi.IN_QUERY, description="Дата в формате YYYY-MM-DD",
                type=openapi.TYPE_STRING, required=True
            )
        ],
        responses={200: LeadSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def by_week(self, request):
        date_str = request.query_params.get('date')
        if not date_str:
            return Response({"error": "Дата не передана"}, status=status.HTTP_400_BAD_REQUEST)

        selected_date = parse_date(date_str)
        if not selected_date:
            return Response({"error": "Некорректный формат даты"}, status=status.HTTP_400_BAD_REQUEST)

        start_of_week = selected_date - timedelta(days=selected_date.weekday())  # Понедельник
        end_of_week = start_of_week + timedelta(days=6)  # Воскресенье

        leads = Lead.objects.filter(date_time__date__range=[start_of_week, end_of_week])
        serializer = LeadSerializer(leads, many=True)

        return Response(serializer.data)

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'date', openapi.IN_QUERY, description="Дата в формате YYYY-MM-DD",
                type=openapi.TYPE_STRING, required=True
            )
        ],
        responses={200: LeadSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def by_date(self, request):
        date_str = request.query_params.get('date')
        if not date_str:
            return Response({"error": "Дата не передана"}, status=status.HTTP_400_BAD_REQUEST)

        selected_date = parse_date(date_str)
        if not selected_date:
            return Response({"error": "Некорректный формат даты"}, status=status.HTTP_400_BAD_REQUEST)

        leads = Lead.objects.filter(date_time__date=selected_date)
        serializer = LeadSerializer(leads, many=True)
        return Response(serializer.data)


class LeadConfirmationViewSet(viewsets.ViewSet):
    @swagger_auto_schema(
        responses={200: "Список неподтвержденных лидов"}
    )
    @action(detail=False, methods=['get'])
    def pending(self, request):
        pending_leads = Lead.objects.filter(is_confirmed=False).order_by('-created_at')

        paginator = PageNumberPagination()
        paginated_leads = paginator.paginate_queryset(pending_leads, request)
        data = LeadSerializer(paginated_leads, many=True).data
        return paginator.get_paginated_response(data)

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'lead_ids': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_INTEGER),
                    description="Список ID лидов для подтверждения"
                ),
            },
            required=['lead_ids']
        ),
        responses={200: "Успешно подтверждено", 400: "Ошибка в запросе"}
    )
    @action(detail=False, methods=['post'])
    def confirm(self, request):
        lead_ids = request.data.get('lead_ids', [])

        if not isinstance(lead_ids, list):
            return Response({"error": "Неверный формат данных"}, status=status.HTTP_400_BAD_REQUEST)

        updated_leads = Lead.objects.filter(id__in=lead_ids, is_confirmed=False).update(is_confirmed=True)

        return Response({
            "message": f"Успешно подтверждено {updated_leads} лидов"
        })
