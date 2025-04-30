from datetime import timedelta
import re
from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings

User = settings.AUTH_USER_MODEL

class Client(models.Model):
    phone = models.CharField(max_length=20, unique=True, verbose_name="Номер телефона")
    name = models.CharField(max_length=255, verbose_name="Имя клиента")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"

    def __str__(self):
        return f"{self.name} ({self.phone})"


class Service(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="Название услуги")
    duration = models.IntegerField(verbose_name="Длительность (мин)", default=30)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=500)
    image = models.ImageField(upload_to='services/', null=True, blank=True)
    is_long = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"

    def __str__(self):
        return self.name


class Lead(models.Model):
    REMINDER_CHOICES = (
        (30, "За 30 минут"),
        (60, "За 1 час"),
        (120, "За 2 часа"),
        (180, "За 3 часа"),
        (1440, "За 1 день"),
    )
    
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Клиент")
    client_name = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True, related_name='leads')
    master = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name="leads")
    date_time = models.DateTimeField(null=True, blank=True)
    prepayment = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_confirmed = models.BooleanField(default=None, null=True, blank=True)
    date = models.DateField(null=True, blank=True)
    reminder_minutes = models.IntegerField(choices=REMINDER_CHOICES, default=60, verbose_name="Время напоминания")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Лид"
        verbose_name_plural = "Лиды"
        ordering = ['-created_at']
    
    def __str__(self):
        client_info = self.client.name if self.client else self.client_name or self.phone or "Без имени"
        service_name = self.service.name if self.service else "Без услуги"
        master_name = self.master.first_name or self.master.email
        date = self.date_time.strftime("%d.%m.%Y %H:%M") if self.date_time else self.date.strftime("%d.%m.%Y") if self.date else "Нет даты"

        return f"{client_info} - {service_name} у {master_name} ({date})"

    def clean(self):
        from users.models import EmployeeSchedule
        
        super().clean()
        
        if self.service and self.service.is_long:
            if not self.date:
                self.date = self.date_time.date() if self.date_time else None
            return
        
        if self.date_time and self.master:
            weekday = self.date_time.isoweekday()
            
            schedules = EmployeeSchedule.objects.filter(employee=self.master, weekday=weekday)
            
            if not schedules.exists():
                day_name = self.date_time.strftime('%A')
                raise ValidationError(f"Мастер не работает в этот день недели ({day_name})")
            
            schedule = schedules.first()
            start_time = schedule.start_time
            end_time = schedule.end_time
            
            appointment_time = self.date_time.time()
            
            if appointment_time < start_time or appointment_time > end_time:
                raise ValidationError(f"Время записи {appointment_time} вне рабочего графика мастера "
                                    f"({start_time} - {end_time}) на {self.date_time.strftime('%A')}")
            
            if self.service:
                service_end_time = (self.date_time + timedelta(minutes=self.service.duration)).time()
                if service_end_time > end_time:
                    raise ValidationError(f"Услуга {self.service.name} (длительность {self.service.duration} мин) "
                                        f"не вместится в рабочее время мастера до {end_time}")
        
    def save(self, *args, **kwargs):
        if self.service and self.service.is_long and not self.date_time and self.date:
            self.full_clean(exclude=["date_time", "service"])
        else:
            self.full_clean(exclude=["service"])
    
        if not self.client and self.phone:
            client, created = Client.objects.get_or_create(
                phone=self.phone,
                defaults={'name': self.client_name or "Неизвестный"}
            )
            self.client = client
    
        is_new = self.pk is None
        super().save(*args, **kwargs)
    
        if self.service and self.service.is_long:
            return
    
        if self.date_time and self.master and self.service:
            if Lead.objects.filter(
                date_time=self.date_time,
                master=self.master,
                service=self.service
            ).exclude(pk=self.pk).exists():
                raise ValidationError(f"У этого мастера уже есть запись на {self.date_time} для услуги {self.service.name}.")
            
            if not self.master.services.filter(id=self.service.id).exists():
                raise ValidationError(f"Мастер {self.master} не оказывает услугу {self.service.name}.")
            
            PRE_APPOINTMENT_BUFFER = timedelta(minutes=30)
            POST_APPOINTMENT_BUFFER = timedelta(minutes=10)
            
            service_duration = timedelta(minutes=self.service.duration)
            appointment_end = self.date_time + service_duration
            
            same_day_appointments = Lead.objects.filter(
                master=self.master,
                date_time__date=self.date_time.date()
            ).exclude(pk=self.pk)
            
            for existing_lead in same_day_appointments:
                if existing_lead.service:
                    existing_service_duration = timedelta(minutes=existing_lead.service.duration)
                    
                    busy_start = existing_lead.date_time - PRE_APPOINTMENT_BUFFER
                    busy_end = existing_lead.date_time + existing_service_duration + POST_APPOINTMENT_BUFFER
                    
                    if (self.date_time < busy_end and appointment_end > busy_start):
                        raise ValidationError(
                            f"Это время пересекается с существующей записью на {existing_lead.date_time} "
                            f"(учитывая буфер 30 минут до и 10 минут после записи)."
                        )
