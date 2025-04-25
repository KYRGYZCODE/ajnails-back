from datetime import datetime, timedelta
from rest_framework import status, filters
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from django.utils.timezone import make_aware
from django.db.models import Q
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi


from leads.models import Lead, Service
from .models import User, EmployeeSchedule
from .serializers import CustomTokenObtainPairSerializer, CustomTokenRefreshSerializer, UserChangePassword, UserRegistration, UserSerializer, FireUser, EmployeeScheduleSerializer, ScheduleListSerializer, EmployeeScheduleUpdateSerializer


class EmployeeListView(ListAPIView):
    serializer_class = UserSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    
    def get_queryset(self):
        service_id = self.request.query_params.get('service_id')
        date_str = self.request.query_params.get('date')
        time_str = self.request.query_params.get('time')
        
        if not service_id:
            return User.objects.none()
            
        queryset = User.objects.filter(
            is_active=True, 
            is_employee=True,
            services__id=service_id
        )
            
        if date_str and time_str:
            try:
                input_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                input_time = datetime.strptime(time_str, '%H:%M').time()
                date_time = datetime.combine(input_date, input_time)
                date_time = make_aware(date_time)
                
                try:
                    service = Service.objects.get(id=service_id)
                    service_duration = timedelta(minutes=service.duration)
                    
                    appointment_end = date_time + service_duration
                    weekday = input_date.isoweekday()
                    
                    available_masters = queryset.filter(schedule__weekday=weekday)
                    
                    available_master_ids = []
                    for master in available_masters:
                        schedules = EmployeeSchedule.objects.filter(
                            employee=master, 
                            weekday=weekday
                        )
                        if schedules.exists():
                            schedule = schedules.first()
                            schedule_start_time = make_aware(datetime.combine(input_date, schedule.start_time))
                            schedule_end_time = make_aware(datetime.combine(input_date, schedule.end_time))

                            if (input_time >= schedule_start_time.time() and (date_time + service_duration) <= schedule_end_time):
                                
                                PRE_APPOINTMENT_BUFFER = timedelta(minutes=30)
                                POST_APPOINTMENT_BUFFER = timedelta(minutes=10)
                                
                                existing_appointments = Lead.objects.filter(
                                    master=master,
                                    date_time__date=input_date
                                )
                                
                                is_available = True
                                for appt in existing_appointments:
                                    if appt.service:
                                        busy_start = make_aware(appt.date_time - PRE_APPOINTMENT_BUFFER)
                                        busy_end = make_aware(appt.date_time + timedelta(minutes=appt.service.duration) + POST_APPOINTMENT_BUFFER)

                                        if (date_time < busy_end and appointment_end > busy_start):
                                            is_available = False
                                            break
                                
                                if is_available:
                                    available_master_ids.append(master.uuid)
                    
                    queryset = queryset.filter(uuid__in=available_master_ids)
                    
                except Service.DoesNotExist:
                    return User.objects.none()
                    
            except ValueError:
                return Response(
                    {"error": "Invalid date or time format. Use YYYY-MM-DD for date and HH:MM for time."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            return queryset

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'service_id',
                openapi.IN_QUERY,
                description="ID of the selected service (required)",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
            openapi.Parameter(
                'date',
                openapi.IN_QUERY,
                description="Date in YYYY-MM-DD format",
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                'time',
                openapi.IN_QUERY,
                description="Time in HH:MM format",
                type=openapi.TYPE_STRING
            ),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class UserViewSet(ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action in ('set_current_warehouse'):
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()
        is_employee = self.request.query_params.get("is_employee")
        project_id = self.request.query_params.get("project_id")
        show_fired = self.request.query_params.get("show_fired")

        if project_id:
            queryset = queryset.filter(projectaccess__project_id=project_id)
        
        if show_fired:
            queryset = queryset.filter(is_fired=True)
        else:
            queryset = queryset.filter(is_active=True)

        if is_employee:
            queryset = queryset.filter(is_employee=True)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'fire':
            return FireUser
        elif self.action == 'register_user':
            return UserRegistration
        elif self.action == 'change_password':
            return UserChangePassword
        elif self.action == 'add_schedule':
            return ScheduleListSerializer
        elif self.action == 'partial_update':
            return EmployeeScheduleUpdateSerializer
        return super().get_serializer_class()

    
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'is_employee',
                openapi.IN_QUERY,
                description="Filter employee users",
                type=openapi.TYPE_BOOLEAN,
                required=False
            )
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @action(methods=['post'], detail=True)
    def fire(self, request, pk=None):
        user = get_object_or_404(User, pk=pk)
        termination_reason = request.data.get('termination_reason')
        termination_order_date = request.data.get('termination_order_date')
        termination_date = request.data.get('termination_date')
        user.fire(reason=termination_reason, order_date=termination_order_date, termination_date=termination_date)
        return Response({'message': 'user fired'}, status=status.HTTP_200_OK)
    
    @action(methods=['post'], detail=True)
    def restore(self, request, pk=None):
        user = get_object_or_404(User, pk=pk, is_fired=True)
        user.restore()
        return Response({'message': 'user restored'}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'])
    def register_user(self, request):
        serializer = UserRegistration(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def change_password(self, request, pk=None):
        user = get_object_or_404(User, pk=pk)
        user.set_password(request.data.get('new_password'))
        user.save()
        return Response({'message': 'Password changed'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def add_schedule(self, request, pk=None):
        user = get_object_or_404(User, pk=pk)
        serializer = ScheduleListSerializer(data=request.data, context={'user': user})
        if serializer.is_valid():
            serializer.save()
            return Response({'status': 'Расписания добавлены'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)



class RegisterView(APIView):
    @swagger_auto_schema(
        operation_summary="Регистрация",
        operation_description='Регистрация пользователей. Письмо на почту не отправляется, юзер является активным.\nОбязательные поля: email, password. Поле role можно указать из этих вариантов: ["worker", "manager", "director"], по умолчанию worker.',
        request_body=UserRegistration,
    )
    def post(self, request):
        serializer = UserRegistration(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)

            return Response({
                    'user': serializer.data,
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }
                }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class CustomTokenRefreshView(TokenRefreshView):
    serializer_class = CustomTokenRefreshSerializer


class EmployeeScheduleViewSet(ModelViewSet):
    queryset = EmployeeSchedule.objects.all()
    serializer_class = EmployeeScheduleSerializer
