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

from users.models import EmployeeSchedule
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

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'date', 
                openapi.IN_QUERY, 
                description="Дата для получения свободных слотов (формат YYYY-MM-DD)",
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'master_id', 
                openapi.IN_QUERY, 
                description="ID мастера",
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'service_id', 
                openapi.IN_QUERY, 
                description="ID услуги",
                type=openapi.TYPE_INTEGER,
                required=True
            )
        ],
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'date': openapi.Schema(type=openapi.TYPE_STRING),
                    'master_id': openapi.Schema(type=openapi.TYPE_STRING),
                    'service_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'available_slots': openapi.Schema(
                        type=openapi.TYPE_ARRAY, 
                        items=openapi.Items(type=openapi.TYPE_STRING)
                    )
                }
            ),
            400: "Ошибка в параметрах запроса",
            404: "Мастер или услуга не найдены"
        }
    )
    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def available_slots(self, request):
        date_str = request.query_params.get('date')
        master_id = request.query_params.get('master_id')
        service_id = request.query_params.get('service_id')
        
        PRE_APPOINTMENT_BUFFER = timedelta(minutes=30)
        POST_APPOINTMENT_BUFFER = timedelta(minutes=10)
        
        if not all([date_str, master_id, service_id]):
            return Response(
                {"error": "Требуются параметры date, master_id и service_id"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            input_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            current_date = timezone.now().date()
            if input_date < current_date:
                return Response(
                    {"error": "Невозможно получить слоты на прошедшую дату"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                master = User.objects.get(uuid=master_id, is_active=True, is_employee=True)
            except User.DoesNotExist:
                return Response(
                    {"error": "Мастер не найден"},
                    status=status.HTTP_404_NOT_FOUND
                )
                
            try:
                service = Service.objects.get(id=service_id)
            except Service.DoesNotExist:
                return Response(
                    {"error": "Услуга не найдена"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            if not master.services.filter(id=service_id).exists():
                return Response(
                    {"error": f"Мастер {master} не предоставляет услугу {service.name}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            weekday = input_date.isoweekday()
            
            schedules = EmployeeSchedule.objects.filter(employee=master, weekday=weekday)
            
            if not schedules.exists():
                day_name = input_date.strftime('%A')
                return Response(
                    {"error": f"Мастер не работает в этот день недели ({day_name})"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            schedule = schedules.first()
            start_time = schedule.start_time
            end_time = schedule.end_time
            
            all_slots = []
            current_time = datetime.combine(input_date, start_time)
            day_end = datetime.combine(input_date, end_time)
            
            service_duration = timedelta(minutes=service.duration)
            slot_interval = timedelta(minutes=10)
            
            now = timezone.now()
            today = now.date()
            
            while current_time + service_duration <= day_end:
                if input_date == today and current_time.time() <= now.time():
                    current_time += slot_interval
                    continue
                    
                all_slots.append(current_time)
                current_time += slot_interval
            
            busy_leads = Lead.objects.filter(
                master=master,
                date_time__date=input_date
            )
            
            busy_periods = []
            for lead in busy_leads:
                if lead.service:
                    busy_start = lead.date_time - PRE_APPOINTMENT_BUFFER
                    busy_end = lead.date_time + timedelta(minutes=lead.service.duration) + POST_APPOINTMENT_BUFFER

                    busy_start = make_aware(busy_start)
                    busy_end = make_aware(busy_end)
                    
                    busy_periods.append((busy_start, busy_end))
            
            available_slots = []
            for slot in all_slots:
                slot_aware = make_aware(slot)
                slot_end = slot_aware + service_duration
                
                is_slot_available = True
                for busy_start, busy_end in busy_periods:
                    if (slot_aware < busy_end and slot_end > busy_start):
                        is_slot_available = False
                        break
                
                if is_slot_available:
                    available_slots.append(slot.strftime('%H:%M'))
            
            return Response({
                'date': date_str,
                'master_id': master_id,
                'service_id': service_id,
                'available_slots': available_slots
            })
            
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
        pending_leads = Lead.objects.filter(is_confirmed=None).order_by('-created_at')

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

        updated_leads = Lead.objects.filter(id__in=lead_ids, is_confirmed=None).update(is_confirmed=True)

        return Response({
            "message": f"Успешно подтверждено {updated_leads} лидов"
        })
    
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'lead_ids': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_INTEGER),
                    description="Список ID лидов для отклонения"
                ),
            },
            required=['lead_ids']
        ),
        responses={200: "Успешно подтверждено", 400: "Ошибка в запросе"}
    )
    @action(detail=False, methods=['post'])
    def reject(self, request):
        lead_ids = request.data.get('lead_ids', [])

        if not isinstance(lead_ids, list):
            return Response({"error": "Неверный формат данных"}, status=status.HTTP_400_BAD_REQUEST)

        updated_leads = Lead.objects.filter(id__in=lead_ids, is_confirmed=None).update(is_confirmed=False)

        return Response({
            "message": f"Успешно отклонено {updated_leads} лидов"
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


class AverageBookingsReportView(APIView):
    @swagger_auto_schema(
        operation_description="Генерация отчета о среднем количестве записей за день, неделю или месяц",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'type': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Тип отчета: day, week, month (по умолчанию 'month')",
                    enum=['week', 'month'],
                ),
                'date': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Дата в формате YYYY-MM-DD (по умолчанию сегодняшняя)",
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
                        'total_bookings': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'days_in_period': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'average_bookings_per_day': openapi.Schema(type=openapi.TYPE_NUMBER, format='float'),
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
        },
        tags=['Отчеты по записям']
    )
    def post(self, request, *args, **kwargs):
        try:
            data = request.data
            report_type = data.get('type', 'month')
            if report_type not in ['week', 'month']:
                return Response({'error': 'Неверный тип отчета. Используй day, week или month.'}, status=400)

            date_str = data.get('date')
            base_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else timezone.now().date()

            if report_type == 'week':
                start_date = base_date - timedelta(days=base_date.weekday())
                end_date = start_date + timedelta(days=6)

            elif report_type == 'month':
                start_date = base_date.replace(day=1)
                end_date = (start_date + relativedelta(months=1)) - timedelta(days=1)

            period_days = (end_date - start_date).days + 1
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())

            leads = Lead.objects.filter(date_time__range=(start_datetime, end_datetime))
            total_bookings = leads.count()
            average_bookings_per_day = round(total_bookings / period_days, 2) if period_days > 0 else 0

            return Response({
                'period': {
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                    'type': report_type
                },
                'total_bookings': total_bookings,
                'days_in_period': period_days,
                'average_bookings_per_day': average_bookings_per_day
            })

        except ValueError as e:
            return Response({'error': f'Неверный формат даты: {str(e)}'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        

class LeadsApprovalStatsReportView(APIView):
    @swagger_auto_schema(
        operation_description="Отчет по соотношению одобренных и отклоненных заявок за день, неделю, месяц или свой период",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['type'],
            properties={
                'type': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Тип отчета: day, week, month(по умолчанию 'month')",
                    enum=['day', 'week', 'month']
                ),
                'date': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Дата в формате YYYY-MM-DD (для day/week/month)",
                    format='date'
                ),
                'start_date': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Начало периода",
                    format='date'
                ),
                'end_date': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Конец периода",
                    format='date'
                ),
            }
        ),
        responses={
            200: openapi.Response(
                description="Статистика одобренных и отклоненных лидов",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'period': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'start_date': openapi.Schema(type=openapi.TYPE_STRING),
                                'end_date': openapi.Schema(type=openapi.TYPE_STRING),
                                'type': openapi.Schema(type=openapi.TYPE_STRING),
                            }
                        ),
                        'total': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'approved': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'rejected': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'approval_rate_percent': openapi.Schema(type=openapi.TYPE_NUMBER, format='float'),
                        'rejection_rate_percent': openapi.Schema(type=openapi.TYPE_NUMBER, format='float'),
                    }
                )
            )
        },
        tags=['Отчеты по записям']
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

            leads = Lead.objects.filter(date_time__range=(start_datetime, end_datetime))
            approved = leads.filter(is_confirmed=True).count()
            rejected = leads.filter(is_confirmed=False).count()
            total = approved + rejected

            approval_rate = round((approved / total) * 100, 2) if total > 0 else 0
            rejection_rate = round((rejected / total) * 100, 2) if total > 0 else 0

            return Response({
                'period': {
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                    'type': report_type
                },
                'total': total,
                'approved': approved,
                'rejected': rejected,
                'approval_rate_percent': approval_rate,
                'rejection_rate_percent': rejection_rate
            })

        except ValueError as e:
            return Response({'error': f'Неверный формат даты: {str(e)}'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=500)