import json
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.http import QueryDict

from .models import WEEKDAY_RUSSIAN, User, EmployeeSchedule
from leads.models import Service

class CSVListField(serializers.ListField):
    """
    Принимает либо:
      - форму "48,51,52" (str) -> split(',') -> ['48','51','52']
      - повторяющиеся поля: ['48','51','52']
    И дальше валидирует каждый элемент через child.
    """
    def to_internal_value(self, data):
        # если получили строку, разбиваем по запятым
        if isinstance(data, str):
            data = [item.strip() for item in data.split(',') if item.strip()]
        return super().to_internal_value(data)


class UserSerializer(serializers.ModelSerializer):
    services = CSVListField(
        child=serializers.PrimaryKeyRelatedField(queryset=Service.objects.all()),
        write_only=True,
        required=False
    )
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        exclude = (
            'groups', 'user_permissions',
            'is_active', 'is_staff', 'is_superuser',
            'last_login'
        )

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Пользователь с таким email уже существует.")
        return value

    def create(self, validated_data):
        services = validated_data.pop('services', None)
        user = User.objects.create_user(**validated_data)
        if services is not None:
            user.services.set(services)
        return user

    def update(self, instance, validated_data):
        # удаляем старый аватар, если прислали avatar=null
        if validated_data.get('avatar') is None and instance.avatar:
            instance.avatar.delete(save=False)
            instance.avatar = None

        services = validated_data.pop('services', None)
        instance = super().update(instance, validated_data)
        if services is not None:
            instance.services.set(services)
        return instance

    def to_representation(self, instance):
        from leads.serializers import ServiceSerializer
        rep = super().to_representation(instance)
        rep['services'] = ServiceSerializer(instance.services, many=True).data
        if instance.schedule.exists():
            rep['schedule'] = EmployeeScheduleSerializer(instance.schedule, many=True).data
        return rep


class UserGet(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('uuid', 'avatar', 'first_name', 'last_name', 'surname', 'email', 'about')


class FireUser(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('termination_reason', 'termination_order_date', 'termination_date')

class UserChangePassword(serializers.Serializer):
    new_password = serializers.CharField()

class UserRegistration(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = UserSerializer(self.user).data
        return data
    

class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        
        refresh_token = RefreshToken(attrs['refresh'])
        user_id = refresh_token['user_id']
        
        try:
            user = User.objects.get(uuid=user_id)
        except User.DoesNotExist:
            raise serializers.ValidationError("Пользователь не найден.")
        
        new_refresh = RefreshToken.for_user(user)
        
        data['refresh'] = str(new_refresh)
        return data


class EmployeeScheduleSerializer(serializers.ModelSerializer):

    class Meta:
        model = EmployeeSchedule
        fields = '__all__'
        extra_kwargs = {
            'employee': {'write_only': True}
        }

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['weekday_name'] = instance.get_weekday_display()
        representation['weekday_name_russian'] = WEEKDAY_RUSSIAN[instance.weekday]
        return representation
    
    def validate(self, attrs):
        if attrs['start_time'] >= attrs['end_time']:
            raise serializers.ValidationError('Время начала должно быть раньше времени окончания.')
        employee = attrs.get('employee')
        weekday = attrs.get('weekday')

        qs = EmployeeSchedule.objects.filter(employee=employee, weekday=weekday)

        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError({
                'weekday': 'Для этого сотрудника уже есть расписание в этот день недели.'
            })

        return attrs


class ScheduleCreation(serializers.ModelSerializer):
    class Meta:
        model = EmployeeSchedule
        fields = ('weekday', 'start_time', 'end_time')

class ScheduleListSerializer(serializers.Serializer):
    schedules = ScheduleCreation(many=True)

    def validate_schedules(self, value):
        seen_weekdays = set()
        for schedule in value:
            weekday = schedule['weekday']
            if weekday in seen_weekdays:
                raise serializers.ValidationError(f"Дублирующийся день недели: {weekday}")
            seen_weekdays.add(weekday)
        return value

    def create(self, validated_data):
        user = self.context.get('user')
        schedules_data = validated_data['schedules']

        for schedule in schedules_data:
            schedule['employee'] = user

        return EmployeeSchedule.objects.bulk_create([
            EmployeeSchedule(**data) for data in schedules_data
        ])

class EmployeeScheduleUpdateSerializer(serializers.ModelSerializer):
    schedules = serializers.ListField(child=serializers.DictField(), write_only=True, required=False)
    delete_schedules = serializers.ListField(write_only=True, required=False)
    update_schedules = serializers.ListField(child=serializers.DictField(), write_only=True, required=False)

    class Meta:
        model = User
        fields = '__all__'
    
    def to_internal_value(self, data):
        data = data.copy()
        json_fields = ['schedules', 'delete_schedules', 'update_schedules']

        for key in json_fields:
            if key in data and isinstance(data[key], str):
                try:
                    data[key] = json.loads(data[key])
                except:
                    raise serializers.ValidationError({key: 'Неверный формат JSON'})

        services = data.get('services')
        if isinstance(services, str):
            try:
                data['services'] = [int(s) for s in services.split(',') if s]
            except ValueError:
                raise serializers.ValidationError({'services': 'Неверный формат списка услуг'})

        return super().to_internal_value(data)
    
    def update(self, instance, validated_data):
        new_schedules = validated_data.pop('schedules', [])
        delete_schedules = validated_data.pop('delete_schedules', [])
        update_schedules = validated_data.pop('update_schedules', [])

        if delete_schedules:
            EmployeeSchedule.objects.filter(id__in=delete_schedules, employee=instance).delete()
        
        for schedule in new_schedules:
            EmployeeSchedule.objects.create(employee=instance, **schedule)
    
        if update_schedules:
            for schedule_data in update_schedules:
                schedule_id = schedule_data.get('id')
                try:
                    employee_schedule = EmployeeSchedule.objects.get(id=schedule_id, employee=instance)
                    for key, value in schedule_data.items():
                        setattr(employee_schedule, key, value)
                    employee_schedule.save()
                except EmployeeSchedule.DoesNotExist:
                    raise serializers.ValidationError({'update_schedules': f'Расписание с ID {schedule_id} не найдено.'})
                
        return super().update(instance, validated_data)
    
