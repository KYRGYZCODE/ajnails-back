from datetime import timedelta
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.utils.timezone import now
from django.db.models import Q
from django.utils.dateparse import parse_date
from django.contrib.auth import get_user_model
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from .models import Client, Service, Lead
from .serializers import ClientSerializer, ServiceSerializer,  LeadSerializer
from users.serializers import UserGet

from django.utils.timezone import make_aware, datetime

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
            'date', 
            openapi.IN_QUERY, 
            description="Дата для получения недельного расписания (формат YYYY-MM-DD)",
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'master_id', 
            openapi.IN_QUERY, 
            description="ID мастера для фильтрации",
            type=openapi.TYPE_STRING,
            required=False
        ),
        openapi.Parameter(
            'service_id', 
            openapi.IN_QUERY, 
            description="ID услуги для фильтрации",
            type=openapi.TYPE_INTEGER,
            required=False
        )
    ],
    responses={
        200: openapi.Response(
            description="Список лидов за неделю",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'days': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'date': openapi.Schema(type=openapi.TYPE_STRING),
                                'day': openapi.Schema(type=openapi.TYPE_STRING),
                                'leads': openapi.Schema(
                                    type=openapi.TYPE_ARRAY, 
                                    items=openapi.Items(type=openapi.TYPE_OBJECT)
                                )
                            }
                        )
                    )
                }
            )
        ),
        400: "Ошибка в формате даты"
        }
    )
    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def weekly_leads(self, request):
        date_str = request.query_params.get('date')
        master_id = request.query_params.get('master_id')
        service_id = request.query_params.get('service_id')
        
        try:
            input_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            monday = input_date - timedelta(days=input_date.weekday())
            
            days_ru = {
                0: 'Понедельник', 
                1: 'Вторник', 
                2: 'Среда', 
                3: 'Четверг', 
                4: 'Пятница', 
                5: 'Суббота', 
                6: 'Воскресенье'
            }
            
            weekly_leads_data = []
            for i in range(7):
                current_day = monday + timedelta(days=i)
                
                day_leads_query = Lead.objects.filter(date_time__date=current_day)
                
                if master_id:
                    day_leads_query = day_leads_query.filter(master_id=master_id)
                    
                if service_id:
                    day_leads_query = day_leads_query.filter(service_id=service_id)
                
                serialized_leads = LeadSerializer(day_leads_query, many=True).data
                
                day_data = {
                    'date': current_day.strftime('%Y-%m-%d'),
                    'day': days_ru[i],
                    'leads': serialized_leads
                }
                
                weekly_leads_data.append(day_data)
            
            return Response({'days': weekly_leads_data})
        
        except ValueError:
            return Response(
                {"error": "Неверный формат даты. Используйте YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST
            )

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'date', 
                openapi.IN_QUERY, 
                description="Дата для получения лидов (формат YYYY-MM-DD)",
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                'master_id', 
                openapi.IN_QUERY, 
                description="ID мастера для фильтрации",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'service_id', 
                openapi.IN_QUERY, 
                description="ID услуги для фильтрации",
                type=openapi.TYPE_INTEGER,
                required=False
            )
        ],
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'date': openapi.Schema(type=openapi.TYPE_STRING),
                    'day': openapi.Schema(type=openapi.TYPE_STRING),
                    'leads': openapi.Schema(
                        type=openapi.TYPE_ARRAY, 
                        items=openapi.Items(type=openapi.TYPE_OBJECT)
                    )
                }
            ),
            400: "Ошибка в формате даты"
        }
    )
    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def daily_leads(self, request):
        date_str = request.query_params.get('date')
        master_id = request.query_params.get('master_id')
        service_id = request.query_params.get('service_id')
        
        try:
            input_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            days_ru = {
                0: 'Понедельник', 
                1: 'Вторник', 
                2: 'Среда', 
                3: 'Четверг', 
                4: 'Пятница', 
                5: 'Суббота', 
                6: 'Воскресенье'
            }
            
            daily_leads_query = Lead.objects.filter(date_time__date=input_date)
            
            if master_id:
                daily_leads_query = daily_leads_query.filter(master_id=master_id)
                
            if service_id:
                daily_leads_query = daily_leads_query.filter(service_id=service_id)
            
            serialized_leads = LeadSerializer(daily_leads_query, many=True).data
            
            day_data = {
                'date': input_date.strftime('%Y-%m-%d'),
                'day': days_ru[input_date.weekday()],
                'leads': serialized_leads
            }
            
            return Response(day_data)
        
        except ValueError:
            return Response(
                {"error": "Неверный формат даты. Используйте YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST
            )
            

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


class FinancialReportView(APIView):
    @swagger_auto_schema(
        operation_description="Генерация финансового отчета за указанный период",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'type': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Тип отчета: day, week, month",
                    enum=['day', 'week', 'month'],
                    default='month'
                ),
                'date': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Дата в формате YYYY-MM-DD (по умолчанию текущая дата)",
                    format='date'
                ),
                'start_date': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Начальная дата периода в формате YYYY-MM-DD",
                    format='date'
                ),
                'end_date': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Конечная дата периода в формате YYYY-MM-DD",
                    format='date'
                ),
            }
        ),
        responses={
            200: openapi.Response(
                description="Отчет успешно создан",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'period': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'start_date': openapi.Schema(type=openapi.TYPE_STRING, format='date'),
                                'end_date': openapi.Schema(type=openapi.TYPE_STRING, format='date'),
                                'type': openapi.Schema(type=openapi.TYPE_STRING),
                            }
                        ),
                        'total_amount': openapi.Schema(type=openapi.TYPE_NUMBER, format='float'),
                    }
                )
            ),
            400: openapi.Response(
                description="Неверные параметры запроса",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            ),
            500: openapi.Response(
                description="Ошибка сервера",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            )
        },
        tags=['Финансовые отчеты']
    )
    def post(self, request, *args, **kwargs):
        try:
            data = request.data
            report_type = 'custom'
            
            if data.get('start_date') and data.get('end_date'):
                start_date = datetime.strptime(data.get('start_date'), '%Y-%m-%d').date()
                end_date = datetime.strptime(data.get('end_date'), '%Y-%m-%d').date()
                report_type = 'custom'
            
            else:
                report_type = data.get('type', 'month')
                
                date_str = data.get('date')
                if date_str:
                    base_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                else:
                    base_date = timezone.now().date()
                
                if report_type == 'day':
                    start_date = base_date
                    end_date = base_date
                
                elif report_type == 'week':
                    start_date = base_date - timedelta(days=base_date.weekday())
                    end_date = start_date + timedelta(days=6)
                
                elif report_type == 'month':
                    start_date = base_date.replace(day=1)
                    next_month = base_date + relativedelta(months=1)
                    end_date = (next_month.replace(day=1) - timedelta(days=1))
                
                else:
                    return Response({
                        'error': f'Неверный тип отчета: {report_type}. Должен быть "day", "week" или "month"'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            
            leads = Lead.objects.filter(
                is_confirmed=True,
                date_time__gte=start_datetime,
                date_time__lte=end_datetime
            )
            
            total_amount = Decimal('0.00')
            for lead in leads:
                for service in lead.service.all():
                    total_amount += service.price
            
            return Response({
                'period': {
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                    'type': report_type
                },
                'total_amount': float(total_amount)
            })
            
        except ValueError as e:
            return Response({
                'error': f'Ошибка формата даты: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NewClientsReportView(APIView):
    @swagger_auto_schema(
        operation_description="Генерация отчета о новых клиентах за указанный период",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'type': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Тип отчета: day, week, month",
                    enum=['day', 'week', 'month'],
                    default='month'
                ),
                'date': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Дата в формате YYYY-MM-DD (по умолчанию текущая дата)",
                    format='date'
                ),
                'start_date': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Начальная дата периода в формате YYYY-MM-DD",
                    format='date'
                ),
                'end_date': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Конечная дата периода в формате YYYY-MM-DD",
                    format='date'
                ),
            }
        ),
        responses={
            200: openapi.Response(
                description="Отчет успешно создан",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'period': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'start_date': openapi.Schema(type=openapi.TYPE_STRING, format='date'),
                                'end_date': openapi.Schema(type=openapi.TYPE_STRING, format='date'),
                                'type': openapi.Schema(type=openapi.TYPE_STRING),
                            }
                        ),
                        'new_clients_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                    }
                )
            ),
            400: openapi.Response(
                description="Неверные параметры запроса",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            ),
            500: openapi.Response(
                description="Ошибка сервера",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            )
        },
        tags=['Отчеты по клиентам']
    )
    def post(self, request, *args, **kwargs):
        try:
            data = request.data
            report_type = 'custom'
            
            if data.get('start_date') and data.get('end_date'):
                start_date = datetime.strptime(data.get('start_date'), '%Y-%m-%d').date()
                end_date = datetime.strptime(data.get('end_date'), '%Y-%m-%d').date()
                report_type = 'custom'
            
            else:
                report_type = data.get('type', 'month')
                
                date_str = data.get('date')
                if date_str:
                    base_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                else:
                    base_date = timezone.now().date()
                
                if report_type == 'day':
                    start_date = base_date
                    end_date = base_date
                
                elif report_type == 'week':
                    start_date = base_date - timedelta(days=base_date.weekday())
                    end_date = start_date + timedelta(days=6)
                
                elif report_type == 'month':
                    start_date = base_date.replace(day=1)
                    next_month = base_date + relativedelta(months=1)
                    end_date = (next_month.replace(day=1) - timedelta(days=1))
                
                else:
                    return Response({
                        'error': f'Неверный тип отчета: {report_type}. Должен быть "day", "week" или "month"'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            
            new_clients_count = Client.objects.filter(
                created_at__gte=start_datetime,
                created_at__lte=end_datetime
            ).count()
            
            return Response({
                'period': {
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                    'type': report_type
                },
                'new_clients_count': new_clients_count
            })
            
        except ValueError as e:
            return Response({
                'error': f'Ошибка формата даты: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)