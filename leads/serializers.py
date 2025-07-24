import asyncio
from datetime import timedelta
from rest_framework import serializers
from django.utils import timezone
from django.db.models import Sum, F

from leads.tasks import check_payment_status
from users.models import EmployeeSchedule
from users.utils import send_order_message
from .models import Service, Lead, Client
from users.serializers import UserGet


class ServiceBaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = '__all__'


class ServiceSerializer(serializers.ModelSerializer):
    additional_services = ServiceBaseSerializer(many=True, read_only=True)
    parent_services = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.all(), many=True, required=False
    )

    class Meta:
        model = Service
        fields = '__all__'

    def to_internal_value(self, data):
        if isinstance(data, QueryDict):
            data = data.copy()

            raw = data.get('parent_services')
            if raw is not None:
                if raw.startswith('[') and raw.endswith(']'):
                    try:
                        lst = json.loads(raw)
                        data.setlist('parent_services', [str(x) for x in lst])
                    except json.JSONDecodeError:
                        pass
                elif ',' in raw:
                    data.setlist('parent_services', [x for x in raw.split(',') if x])
                else:
                    data.setlist('parent_services', data.getlist('parent_services'))

        return super().to_internal_value(data)

    def create(self, validated_data):
        parents = validated_data.pop('parent_services', None)
        service = Service.objects.create(**validated_data)
        if parents:
            service.parent_services.set(parents)
        return service

    def update(self, instance, validated_data):
        parents = validated_data.pop('parent_services', None)
        instance = super().update(instance, validated_data)
        if parents is not None:
            instance.parent_services.set(parents)
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['parent_services'] = ServiceBaseSerializer(
            instance.parent_services.all(), many=True
        ).data
        return representation

    def validate(self, attrs):
        instance = self.instance
        parents = attrs.get("parent_services")
        if instance and parents is None:
            parents = instance.parent_services.all()

        if parents and instance:
            for parent in parents:
                if parent == instance:
                    raise serializers.ValidationError({"parent_services": "Услуга не может быть родителем сама себе."})

                stack = [parent]
                visited = set()
                while stack:
                    current = stack.pop()
                    if current in visited:
                        continue
                    visited.add(current)
                    if current == instance:
                        raise serializers.ValidationError({"parent_services": "Циклическая связь между услугами недопустима."})
                    stack.extend(list(current.parent_services.all()))
        return attrs

class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = '__all__'

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['visits_count'] = Lead.objects.filter(client=instance).count()
        representation['total_sum'] = Lead.objects.aggregate(total=Sum(F('services__price')))['total'] or 0
 
        return representation


class LeadSerializer(serializers.ModelSerializer):
    services = serializers.PrimaryKeyRelatedField(queryset=Service.objects.all(), many=True)

    class Meta:
        model = Lead
        fields = '__all__'


    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['services'] = ServiceSerializer(instance.services.all(), many=True).data
        representation['master'] = UserGet(instance.master).data
        representation['client'] = ClientSerializer(instance.client).data if instance.client else None
        date_field = instance.date if instance.date else instance.date_time
        representation['weekday'] = date_field.isoweekday()
        return representation
    
    def validate(self, data):
        date_time = data.get('date_time')
        master = data.get('master')
        services = data.get('services') or (self.instance.services.all() if self.instance else [])
        date = data.get('date')

        if any(s.is_long for s in services):
            if not date and not date_time:
                raise serializers.ValidationError("Для сложной услуги необходимо указать хотя бы дату")
            
            if not master:
                raise serializers.ValidationError("Необходимо указать мастера")
                
            if date and not date_time:
                current_date = timezone.now().date()
                if date < current_date:
                    raise serializers.ValidationError("Невозможно создать запись на прошедшую дату")
                    
                weekday = date.isoweekday()
                schedules = EmployeeSchedule.objects.filter(employee=master, weekday=weekday)
                if not schedules.exists():
                    day_name = date.strftime('%A')
                    raise serializers.ValidationError(f"Мастер не работает в этот день недели ({day_name})")
                
                return data
        
        total_duration = sum(s.duration for s in services)

        if not date_time or not master:
            return data
        
        current_datetime = timezone.now()
        if date_time < current_datetime:
            raise serializers.ValidationError("Невозможно создать запись на прошедшую дату и время")
            
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
        
        if total_duration:
            service_end_time = (date_time + timedelta(minutes=total_duration)).time()
            if service_end_time > end_time:
                raise serializers.ValidationError("Услуги не помещаются в рабочее время мастера")
                                                
        if 'id' in self.context.get('view', {}).kwargs if self.context.get('view') else {}:
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
            if existing_lead.services.exists():
                existing_duration = sum(s.duration for s in existing_lead.services.all())
                existing_service_duration = timedelta(minutes=existing_duration)
                
                busy_start = existing_lead.date_time - PRE_APPOINTMENT_BUFFER
                busy_end = existing_lead.date_time + existing_service_duration + POST_APPOINTMENT_BUFFER
                
                new_end = date_time + timedelta(minutes=total_duration)
                
                if (date_time < busy_end and new_end > busy_start):
                    raise serializers.ValidationError(
                        f"Это время пересекается с существующей записью на {existing_lead.date_time} "
                        f"(учитывая буфер 30 минут до и 10 минут после записи)."
                    )
                    
        return data
    
    def create(self, validated_data):
        services = validated_data.pop('services', [])
        lead = Lead.objects.create(**validated_data)
        if services:
            lead.services.set(services)

        client_name = lead.client.name if lead.client else lead.client_name or "Без имени"
        phone = lead.phone or "—"
        service_names = ", ".join(s.name for s in lead.services.all())
        master_name = lead.master.first_name or lead.master.email

        is_long_service = any(s.is_long for s in lead.services.all())

        if is_long_service and not lead.date_time:
            date_str = lead.date.strftime("%d.%m.%Y") if lead.date else "Дата не указана"
            date_info = f"Дата: *{date_str}* (Менеджер перезвонит для уточнения времени)"
        else:
            date_str = lead.date_time.strftime("%d.%m.%Y %H:%M") if lead.date_time else "Время не указано"
            date_info = f"Дата и время: *{date_str}*"

        reminder_text = dict(Lead.REMINDER_CHOICES).get(lead.reminder_minutes, "За 1 час")

        message = (
            f"📥 *Новая запись!*\n"
            f"👤 Клиент: *{client_name}*\n"
            f"📞 Телефон: `{phone}`\n"
            f"🛠 Услуги: *{service_names}*\n"
            f"🧑‍🔧 Мастер: *{master_name}*\n"
            f"🕒 {date_info}\n"
            f"⏰ Напоминание: *{reminder_text}*\n"
        )

        asyncio.run(send_order_message(message))
        if lead.master.telegram_chat_id:
            asyncio.run(send_order_message(message, [lead.master.telegram_chat_id]))

        try:
            from leads.payment import create_payment_for_lead
            create_payment_for_lead(lead)
            check_payment_status.apply_async(args=[lead.pk], countdown=15)
        except Exception as e:
            print(f"Failed to create payment for lead {lead.pk}: {e}")

        return lead


class BusySlotSerializer(serializers.Serializer):
    date_time = serializers.DateTimeField()
    master_id = serializers.UUIDField()
