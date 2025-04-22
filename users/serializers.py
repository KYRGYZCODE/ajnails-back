from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, EmployeeSchedule

class UserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        exclude = ('groups', 'user_permissions', 'is_active', 'is_staff', 'is_superuser',)
    
    def create(self, validated_data):
        services_data = validated_data.pop('services', None)

        user = User.objects.create_user(**validated_data)

        if services_data:
            user.services.set(services_data)

        return user
    
    def to_representation(self, instance):
        from leads.serializers import ServiceSerializer
        representation = super().to_representation(instance)
        representation["services"] = ServiceSerializer(instance.services, many=True).data
        if instance.schedule.exists():
            representation['schedule'] = EmployeeScheduleSerializer(instance.schedule, many=True).data
        return representation

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