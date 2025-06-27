from datetime import date, timedelta
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
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
    serializer_class = ServiceSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = Service.objects.all()
        if self.action == "list":
            include_additional = self.request.query_params.get("include_additional")
            if not include_additional:
                queryset = queryset.filter(is_additional=False)
        return queryset


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
                    'service_ids': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(type=openapi.TYPE_INTEGER)
                    ),
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
            slot_interval = timedelta(minutes=30)
            
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
                if lead.services.exists():
                    duration = sum(s.duration for s in lead.services.all())
                    busy_start = lead.date_time - PRE_APPOINTMENT_BUFFER
                    busy_end = lead.date_time + timedelta(minutes=duration) + POST_APPOINTMENT_BUFFER

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


class ServiceAvailableSlotsView(APIView):
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'service_ids',
                openapi.IN_QUERY,
                description="Comma separated IDs of selected services",
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'date', 
                openapi.IN_QUERY, 
                description="Date for available slots (format YYYY-MM-DD)",
                type=openapi.TYPE_STRING,
                required=True
            ),
        ],
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'date': openapi.Schema(type=openapi.TYPE_STRING),
                    'service_ids': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(type=openapi.TYPE_INTEGER)
                    ),
                    'available_slots': openapi.Schema(
                        type=openapi.TYPE_ARRAY, 
                        items=openapi.Items(type=openapi.TYPE_STRING)
                    )
                }
            ),
            400: "Error in request parameters",
            404: "Service not found"
        }
    )
    def get(self, request):
        service_ids_param = request.query_params.get('service_ids')
        date_str = request.query_params.get('date')

        if not all([service_ids_param, date_str]):
            return Response(
                {"error": "service_ids and date are required parameters"},
                status=400
            )

        try:
            service_ids = [int(s) for s in service_ids_param.split(',') if s]
        except ValueError:
            return Response({"error": "Invalid service_ids"}, status=400)

        services = Service.objects.filter(id__in=service_ids)
        if not services.exists():
            return Response({"error": "Service not found"}, status=404)
            
        try:
            input_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            current_date = datetime.now().date()
            if input_date < current_date:
                return Response(
                    {"error": "Cannot get slots for past dates"},
                    status=400
                )
                
            masters = User.objects.filter(is_active=True, is_employee=True)
            for sid in service_ids:
                masters = masters.filter(services__id=sid)
            
            if not masters.exists():
                return Response(
                    {"error": "No masters available for this service"},
                    status=404
                )
                
            weekday = input_date.isoweekday()
            
            schedules = EmployeeSchedule.objects.filter(
                employee__in=masters,
                weekday=weekday
            )
            
            if not schedules.exists():
                return Response(
                    {"error": "No masters working on this day"},
                    status=404
                )

            earliest_start = min(schedule.start_time for schedule in schedules)
            latest_end = max(schedule.end_time for schedule in schedules)
            
            all_slots = []
            slot_duration = 30
            slot_time = datetime.combine(input_date, earliest_start)
            day_end = datetime.combine(input_date, latest_end)
            service_duration = timedelta(minutes=services.duration)
            
            while slot_time + service_duration <= day_end:
                all_slots.append(slot_time)
                slot_time += timedelta(minutes=slot_duration)
                
            leads = Lead.objects.filter(
                master__in=masters,
                date_time__date=input_date
            )
            
            PRE_APPOINTMENT_BUFFER = timedelta(minutes=30)
            POST_APPOINTMENT_BUFFER = timedelta(minutes=10)
            
            busy_periods = []
            for lead in leads:
                if lead.services.exists():
                    duration = sum(s.duration for s in lead.services.all())
                    busy_start = lead.date_time - PRE_APPOINTMENT_BUFFER
                    busy_end = lead.date_time + timedelta(minutes=duration) + POST_APPOINTMENT_BUFFER

                    busy_start = make_aware(busy_start) if not busy_start.tzinfo else busy_start
                    busy_end = make_aware(busy_end) if not busy_end.tzinfo else busy_end

                    busy_periods.append((busy_start, busy_end))
            
            available_slots = []
            for slot in all_slots:
                slot_aware = make_aware(slot) if not slot.tzinfo else slot
                slot_end = slot_aware + service_duration
                
                for master in masters:
                    master_schedules = schedules.filter(employee=master)
                    if not master_schedules.exists():
                        continue
                        
                    schedule = master_schedules.first()
                    if not (slot.time() >= schedule.start_time and 
                           (slot + service_duration).time() <= schedule.end_time):
                        continue
                        
                    is_available = True
                    for busy_start, busy_end in busy_periods:
                        if (slot_aware < busy_end and slot_end > busy_start):
                            master_lead = leads.filter(
                                master=master, 
                                date_time__gte=busy_start,
                                date_time__lte=busy_end
                            ).exists()
                            
                            if master_lead:
                                is_available = False
                                break
                    
                    if is_available:
                        available_slots.append(slot.strftime('%H:%M'))
                        break
            
            return Response({
                'date': date_str,
                'service_ids': service_ids,
                'available_slots': sorted(list(set(available_slots)))
            })
            
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=400
            )

class ServiceMastersWithSlotsView(APIView):
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'service_ids',
                openapi.IN_QUERY,
                description="Comma separated IDs of selected services",
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'date', 
                openapi.IN_QUERY, 
                description="Date for available slots (format YYYY-MM-DD)",
                type=openapi.TYPE_STRING,
                required=True
            ),
        ],
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'date': openapi.Schema(type=openapi.TYPE_STRING),
                    'service_ids': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(type=openapi.TYPE_INTEGER)
                    ),
                    'is_long_service': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'masters': openapi.Schema(
                        type=openapi.TYPE_ARRAY, 
                        items=openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'uuid': openapi.Schema(type=openapi.TYPE_STRING),
                                'name': openapi.Schema(type=openapi.TYPE_STRING),
                                'avatar': openapi.Schema(type=openapi.TYPE_STRING, nullable=True),
                                'available_slots': openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Schema(type=openapi.TYPE_STRING)
                                )
                            }
                        )
                    )
                }
            ),
            400: "Error in request parameters",
            404: "Service not found or no masters available"
        }
    )
    def get(self, request):
        service_ids_param = request.query_params.get('service_ids')
        date_str = request.query_params.get('date')

        if not all([service_ids_param, date_str]):
            return Response(
                {"error": "service_ids and date are required parameters"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            service_ids = [int(s) for s in service_ids_param.split(',') if s]
        except ValueError:
            return Response({"error": "Invalid service_ids"}, status=status.HTTP_400_BAD_REQUEST)

        services = Service.objects.filter(id__in=service_ids)
        if not services.exists():
            return Response({"error": "Services not found"}, status=status.HTTP_404_NOT_FOUND)
            
        try:
            current_datetime = timezone.now()
            current_date = current_datetime.date()
            
            input_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            if input_date < current_date:
                return Response(
                    {"error": "Cannot get slots for past dates"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            masters = User.objects.filter(is_active=True, is_employee=True)
            for sid in service_ids:
                masters = masters.filter(services__id=sid)
            masters = masters.distinct()
            
            if not masters.exists():
                return Response(
                    {"error": "No masters available for this service"},
                    status=status.HTTP_404_NOT_FOUND
                )
                
            weekday = input_date.isoweekday()
            
            master_schedules = EmployeeSchedule.objects.filter(
                employee__in=masters,
                weekday=weekday
            )
            
            if not master_schedules.exists():
                return Response(
                    {"error": "No masters working on this day"},
                    status=status.HTTP_404_NOT_FOUND
                )

            total_duration = sum(s.duration for s in services)
            is_long = any(s.is_long for s in services)

            if is_long:
                result_masters = []
                for master in masters:
                    master_schedule = master_schedules.filter(employee=master).first()
                    if master_schedule:
                        master_data = {
                            'uuid': str(master.uuid),
                            'name': f"{master.first_name} {master.last_name}".strip(),
                            'avatar': request.build_absolute_uri(master.avatar.url) if master.avatar else None,
                            'available_slots': []
                        }
                        result_masters.append(master_data)
                
                return Response({
                    'date': date_str,
                    'service_ids': service_ids,
                    'is_long_service': True,
                    'masters': result_masters
                })

            leads = Lead.objects.filter(
                master__in=masters,
                date_time__date=input_date
            )

            PRE_APPOINTMENT_BUFFER = timedelta(minutes=30)
            POST_APPOINTMENT_BUFFER = timedelta(minutes=10)
            service_duration = timedelta(minutes=total_duration)
            slot_duration = 30
            booking_buffer = timedelta(minutes=30)
            
            result_masters = []
            
            for master in masters:
                master_schedule = master_schedules.filter(employee=master).first()
                if not master_schedule:
                    continue
                
                slot_time = datetime.combine(input_date, master_schedule.start_time)
                day_end = datetime.combine(input_date, master_schedule.end_time)
                
                if timezone.is_naive(slot_time):
                    slot_time = timezone.make_aware(slot_time)
                if timezone.is_naive(day_end):
                    day_end = timezone.make_aware(day_end)
                
                all_slots = []
                while slot_time + service_duration <= day_end:
                    if input_date == current_date:
                        print(f"slot_time: {slot_time}, tzinfo: {slot_time.tzinfo}, type: {type(slot_time)}")
                        print(f"current_datetime + booking_buffer: {current_datetime + booking_buffer}, tzinfo: {(current_datetime + booking_buffer).tzinfo}, type: {type(current_datetime + booking_buffer)}")
                        if slot_time >= (current_datetime + booking_buffer):
                            all_slots.append(slot_time)
                    else:
                        all_slots.append(slot_time)
                        
                    slot_time += timedelta(minutes=slot_duration)
                
                master_leads = leads.filter(master=master)
                busy_periods = []
                
                for lead in master_leads:
                    if lead.services.exists():
                        duration = sum(s.duration for s in lead.services.all())
                        busy_start = lead.date_time - PRE_APPOINTMENT_BUFFER
                        busy_end = lead.date_time + timedelta(minutes=duration) + POST_APPOINTMENT_BUFFER
                        
                        if not busy_start.tzinfo:
                            busy_start = timezone.make_aware(busy_start)
                        if not busy_end.tzinfo:
                            busy_end = timezone.make_aware(busy_end)
                        
                        busy_periods.append((busy_start, busy_end))
                
                available_slots = []
                for slot in all_slots:
                    slot_end = slot + service_duration
                    
                    is_available = True
                    for busy_start, busy_end in busy_periods:
                        if (slot < busy_end and slot_end > busy_start):
                            is_available = False
                            break
                    
                    if is_available:
                        available_slots.append(slot.strftime('%H:%M'))
                
                if available_slots:
                    master_data = {
                        'uuid': str(master.uuid),
                        'name': f"{master.first_name} {master.last_name}".strip(),
                        'avatar': request.build_absolute_uri(master.avatar.url) if master.avatar else None,
                        'available_slots': sorted(available_slots)
                    }
                    result_masters.append(master_data)
            
            return Response({
                'date': date_str,
                'service_ids': service_ids,
                'is_long_service': False,
                'masters': result_masters
            })
            
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST
            )

class AvailableDatesView(APIView):
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'service_ids', 
                openapi.IN_QUERY, 
                description="ID of the selected service",
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'year', 
                openapi.IN_QUERY, 
                description="Selected year",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
            openapi.Parameter(
                'month', 
                openapi.IN_QUERY, 
                description="Selected month (from 1 to 12)",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
        ],
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'month': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'service_ids': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(type=openapi.TYPE_INTEGER)
                    ),
                    'available_dates': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(type=openapi.TYPE_STRING)
                    )
                }
            ),
            400: "Error in request parameters",
            404: "Service not found"
        }
    )
    def get(self, request):
        service_ids_param = request.query_params.get('service_ids')
        month = request.query_params.get('month')
        year = request.query_params.get('year')

        if not all([service_ids_param, month, year]):
            return Response(
                {"error": "service_ids, month and year are required parameters"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            service_ids = [int(s) for s in service_ids_param.split(',') if s]
            month = int(month)
            year = int(year)
        except ValueError:
            return Response(
                {"error": "service_ids, month and year must be integers"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not (1 <= month <= 12):
            return Response(
                {"error": "Month must be between 1 and 12"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        services = Service.objects.filter(id__in=service_ids)
        if not services.exists():
            return Response({"error": "Services not found"}, status=status.HTTP_404_NOT_FOUND)
        
        current_date = datetime.now().date()
        
        first_day = date(year, month, 1)
        
        if month == 12:
            last_day = date(year, 12, 31)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)
        
        masters = User.objects.filter(is_active=True, is_employee=True)
        for sid in service_ids:
            masters = masters.filter(services__id=sid)
        
        if not masters.exists():
            return Response(
                {"error": "No masters available for this service"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        available_dates = []
        current_day = max(first_day, current_date)
        
        while current_day <= last_day:
            weekday = current_day.isoweekday()
            
            master_schedules = EmployeeSchedule.objects.filter(
                employee__in=masters,
                weekday=weekday
            )
            
            if master_schedules.exists():
                if any(s.is_long for s in services):
                    available_dates.append(current_day.strftime('%Y-%m-%d'))
                else:
                    leads = Lead.objects.filter(
                        master__in=masters,
                        date_time__date=current_day
                    )
                    
                    PRE_APPOINTMENT_BUFFER = timedelta(minutes=30)
                    POST_APPOINTMENT_BUFFER = timedelta(minutes=10)
                    service_duration = timedelta(minutes=sum(s.duration for s in services))
                    slot_duration = 30
                    
                    date_has_slots = False
                    
                    for master in masters:
                        master_schedule = master_schedules.filter(employee=master).first()
                        if not master_schedule:
                            continue
                        
                        slot_time = datetime.combine(current_day, master_schedule.start_time)
                        day_end = datetime.combine(current_day, master_schedule.end_time)
                        
                        all_slots = []
                        while slot_time + service_duration <= day_end:
                            all_slots.append(slot_time)
                            slot_time += timedelta(minutes=slot_duration)
                        
                        master_leads = leads.filter(master=master)
                        busy_periods = []
                        
                        for lead in master_leads:
                            if lead.services.exists():
                                duration = sum(s.duration for s in lead.services.all())
                                busy_start = lead.date_time - PRE_APPOINTMENT_BUFFER
                                busy_end = lead.date_time + timedelta(minutes=duration) + POST_APPOINTMENT_BUFFER

                                busy_start = make_aware(busy_start) if not busy_start.tzinfo else busy_start
                                busy_end = make_aware(busy_end) if not busy_end.tzinfo else busy_end

                                busy_periods.append((busy_start, busy_end))
                        
                        for slot in all_slots:
                            slot_aware = make_aware(slot) if not slot.tzinfo else slot
                            slot_end = slot_aware + service_duration
                            
                            is_available = True
                            for busy_start, busy_end in busy_periods:
                                if (slot_aware < busy_end and slot_end > busy_start):
                                    is_available = False
                                    break
                            
                            if is_available:
                                date_has_slots = True
                                break
                        
                        if date_has_slots:
                            break
                    
                    if date_has_slots:
                        available_dates.append(current_day.strftime('%Y-%m-%d'))
            
            current_day += timedelta(days=1)
        
        return Response({
            'month': month,
            'year': year,
            'service_ids': service_ids,
            'available_dates': available_dates
        })


class LeadConfirmationViewSet(viewsets.ViewSet):
    @swagger_auto_schema(
    responses={200: "Список неподтвержденных лидов"})
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
        operation_description="Генерация финансового отчета для графиков по дням или неделям",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'type': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Тип периода: week, month, quarter (макс. 3 месяца)",
                    enum=['week', 'month', 'quarter'],
                    default='month'
                ),
                'date': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Базовая дата в формате YYYY-MM-DD",
                    format='date'
                ),
                'group_by': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Группировка данных: по дням или по неделям',
                    enum=['day', 'week'],
                    default='day'
                )
            }
        ),
        tags=['Финансовые отчеты']
    )
    def post(self, request, *args, **kwargs):
        try:
            data = request.data
            report_type = data.get('type', 'month')
            group_by = data.get('group_by', 'day')
            base_date_str = data.get('date')
            base_date = datetime.strptime(base_date_str, '%Y-%m-%d').date() if base_date_str else timezone.now().date()

            if report_type == 'week':
                start_date = base_date - timedelta(days=base_date.weekday())
                end_date = start_date + timedelta(days=6)
            elif report_type == 'month':
                start_date = base_date.replace(day=1)
                next_month = base_date + relativedelta(months=1)
                end_date = next_month.replace(day=1) - timedelta(days=1)
            elif report_type == 'quarter':
                start_date = base_date.replace(day=1)
                next_quarter = base_date + relativedelta(months=3)
                end_date = next_quarter.replace(day=1) - timedelta(days=1)
            else:
                return Response({'error': f'Неверный тип периода: {report_type}'}, status=400)

            if (end_date - start_date).days > 92:
                return Response({'error': 'Максимальный период — 3 месяца'}, status=400)

            result_data = []

            if group_by == 'day':
                current_date = start_date
                while current_date <= end_date:
                    total = self._get_total_for_range(current_date, current_date)
                    result_data.append({
                        'date': current_date.strftime('%Y-%m-%d'),
                        'total_amount': float(total)
                    })
                    current_date += timedelta(days=1)

            elif group_by == 'week':
                current_start = start_date
                while current_start <= end_date:
                    current_end = min(current_start + timedelta(days=6), end_date)
                    total = self._get_total_for_range(current_start, current_end)
                    result_data.append({
                        'week_start': current_start.strftime('%Y-%m-%d'),
                        'week_end': current_end.strftime('%Y-%m-%d'),
                        'total_amount': float(total)
                    })
                    current_start += timedelta(days=7)
            else:
                return Response({'error': 'Параметр group_by должен быть "day" или "week"'}, status=400)

            return Response({
                'period': {
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                    'type': report_type
                },
                'group_by': group_by,
                'data': result_data
            })

        except ValueError as e:
            return Response({'error': f'Ошибка формата даты: {str(e)}'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    def _get_total_for_range(self, start_date, end_date):
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        leads = Lead.objects.filter(
            is_confirmed=True,
            date_time__gte=start_dt,
            date_time__lte=end_dt
        )

        total = Decimal('0.00')
        for lead in leads:
            total += sum((s.price for s in lead.services.all()), Decimal('0.00'))
        return total

class ClientStatsView(APIView):
    @swagger_auto_schema(
        operation_description="Получить соотношение новых и возвращающихся клиентов за указанный период.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["type"],
            properties={
                "type": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=["day", "week", "month"],
                    description="Тип периода (день, неделя, месяц)",
                    default="month"
                ),
                "date": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="date",
                    description="Дата в формате YYYY-MM-DD (используется как базовая для периода)"
                ),
            }
        ),
        responses={
            200: openapi.Response(
                description="Успешный ответ с данными по клиентам",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "period": openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                "start_date": openapi.Schema(type=openapi.TYPE_STRING, format="date"),
                                "end_date": openapi.Schema(type=openapi.TYPE_STRING, format="date"),
                                "type": openapi.Schema(type=openapi.TYPE_STRING)
                            }
                        ),
                        "data": openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                "new_clients": openapi.Schema(type=openapi.TYPE_INTEGER),
                                "returning_clients": openapi.Schema(type=openapi.TYPE_INTEGER)
                            }
                        )
                    }
                )
            ),
            400: openapi.Response(description="Ошибка запроса"),
            500: openapi.Response(description="Ошибка сервера")
        },
        tags=["Клиенты"]
    )
    def post(self, request, *args, **kwargs):
        try:
            report_type = request.data.get('type', 'month')
            date_str = request.data.get('date')
            if date_str:
                base_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            else:
                base_date = timezone.now().date()

            if report_type == 'day':
                start_date = end_date = base_date
            elif report_type == 'week':
                start_date = base_date - timedelta(days=base_date.weekday())
                end_date = start_date + timedelta(days=6)
            elif report_type == 'month':
                start_date = base_date.replace(day=1)
                next_month = base_date + relativedelta(months=1)
                end_date = next_month.replace(day=1) - timedelta(days=1)
            else:
                return Response({"error": "Неверный тип периода. Используйте 'day', 'week' или 'month'."},
                                status=status.HTTP_400_BAD_REQUEST)

            start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
            end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))

            leads_in_period = Lead.objects.filter(
                is_confirmed=True,
                date_time__range=(start_datetime, end_datetime),
                client__isnull=False
            )

            new_clients = 0
            returning_clients = 0

            for lead in leads_in_period.select_related('client'):
                client = lead.client
                first_lead = Lead.objects.filter(
                    client=client,
                    is_confirmed=True
                ).order_by('date_time').first()

                if first_lead and start_datetime <= first_lead.date_time <= end_datetime:
                    new_clients += 1
                else:
                    returning_clients += 1

            return Response({
                "period": {
                    "start_date": start_date.strftime('%Y-%m-%d'),
                    "end_date": end_date.strftime('%Y-%m-%d'),
                    "type": report_type
                },
                "data": {
                    "new_clients": new_clients,
                    "returning_clients": returning_clients
                }
            })

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TotalClientsView(APIView):
    def get(self, request):
        cleints_count = Client.objects.all().count()
        return Response({'total_clients': cleints_count})

class LeadStatsView(APIView):
    @swagger_auto_schema(
        operation_description="Получить отчет по подтвержденным и неподтвержденным записям за указанный период (неделя/месяц).",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["type"],
            properties={
                "type": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=["week", "month"],
                    description="Тип периода (неделя или месяц)",
                    default="month"
                ),
                "date": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="date",
                    description="Дата в формате YYYY-MM-DD (будет использована как база для периода)"
                ),
            }
        ),
        responses={
            200: openapi.Response(
                description="Успешный ответ с данными по подтвержденным и неподтвержденным записям",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "period": openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                "start_date": openapi.Schema(type=openapi.TYPE_STRING, format="date"),
                                "end_date": openapi.Schema(type=openapi.TYPE_STRING, format="date"),
                                "type": openapi.Schema(type=openapi.TYPE_STRING)
                            }
                        ),
                        "data": openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                "confirmed_leads": openapi.Schema(type=openapi.TYPE_INTEGER),
                                "unconfirmed_leads": openapi.Schema(type=openapi.TYPE_INTEGER)
                            }
                        )
                    }
                )
            ),
            400: openapi.Response(description="Ошибка запроса"),
            500: openapi.Response(description="Ошибка сервера")
        },
        tags=["Записи"]
    )
    def post(self, request, *args, **kwargs):
        try:
            report_type = request.data.get('type', 'month')
            date_str = request.data.get('date')
            if date_str:
                base_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            else:
                base_date = timezone.now().date()

            if report_type == 'week':
                start_date = base_date - timedelta(days=base_date.weekday())
                end_date = start_date + timedelta(days=6)
            elif report_type == 'month':
                start_date = base_date.replace(day=1)
                next_month = base_date + relativedelta(months=1)
                end_date = next_month.replace(day=1) - timedelta(days=1)
            else:
                return Response({"error": "Неверный тип периода. Используйте 'week' или 'month'."},
                                status=status.HTTP_400_BAD_REQUEST)

            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())

            leads_in_period = Lead.objects.filter(
                date_time__range=(start_datetime, end_datetime)
            )

            confirmed_leads = leads_in_period.filter(is_confirmed=True).count()
            unconfirmed_leads = leads_in_period.filter(is_confirmed=False).count()

            return Response({
                "period": {
                    "start_date": start_date.strftime('%Y-%m-%d'),
                    "end_date": end_date.strftime('%Y-%m-%d'),
                    "type": report_type
                },
                "data": {
                    "confirmed_leads": confirmed_leads,
                    "unconfirmed_leads": unconfirmed_leads
                }
            })

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        
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


class MyLeadsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        user = request.user
        leads = Lead.objects.filter(
        master=user
        ).filter(
        Q(is_confirmed=False) | Q(is_confirmed__isnull=True)
        )
        serializer = LeadSerializer(leads, many=True)
        return Response(serializer.data)