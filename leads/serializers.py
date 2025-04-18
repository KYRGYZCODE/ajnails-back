from datetime import timedelta
from rest_framework import serializers

from users.models import EmployeeSchedule
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
    
    def validate(self, data):
        date_time = data.get('date_time')
        master = data.get('master')
        service = data.get('service')
        
        if not date_time or not master:
            return data
            
        weekday = date_time.isoweekday()
        
        schedules = EmployeeSchedule.objects.filter(employee=master, weekday=weekday)
        
        if not schedules.exists():
            day_name = date_time.strftime('%A')
            raise serializers.ValidationError(f"Мастер не работает в этот день недели ({day_name})")
        
        schedule = schedules.first()
        start_time = schedule.start_time
        end_time = schedule.end_time
        
        appointment_time = date_time.time()
        
        if appointment_time < start_time or appointment_time > end_time:
            raise serializers.ValidationError(f"Время записи {appointment_time} вне рабочего графика мастера "
                                             f"({start_time} - {end_time}) на {date_time.strftime('%A')}")
        
        if service:
            service_end_time = (date_time + timedelta(minutes=service.duration)).time()
            if service_end_time > end_time:
                raise serializers.ValidationError(f"Услуга {service.name} (длительность {service.duration} мин) "
                                                f"не вместится в рабочее время мастера до {end_time}")
                                                
        if 'id' in self.context.get('view').kwargs:
            lead_id = self.context.get('view').kwargs['id']
        else:
            lead_id = None
            
        same_day_appointments = Lead.objects.filter(
            master=master,
            date_time__date=date_time.date()
        )
        
        if lead_id:
            same_day_appointments = same_day_appointments.exclude(id=lead_id)
            
        PRE_APPOINTMENT_BUFFER = timedelta(minutes=30)
        POST_APPOINTMENT_BUFFER = timedelta(minutes=10)
        
        for existing_lead in same_day_appointments:
            if existing_lead.service:
                existing_service_duration = timedelta(minutes=existing_lead.service.duration)
                
                busy_start = existing_lead.date_time - PRE_APPOINTMENT_BUFFER
                busy_end = existing_lead.date_time + existing_service_duration + POST_APPOINTMENT_BUFFER
                
                new_end = date_time + timedelta(minutes=service.duration if service else 0)
                
                if (date_time < busy_end and new_end > busy_start):
                    raise serializers.ValidationError(
                        f"Это время пересекается с существующей записью на {existing_lead.date_time} "
                        f"(учитывая буфер 30 минут до и 10 минут после записи)."
                    )
                    
        return data


class BusySlotSerializer(serializers.Serializer):
    date_time = serializers.DateTimeField()
    master_id = serializers.UUIDField()
