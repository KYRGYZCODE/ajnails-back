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
    is_additional = models.BooleanField(default=False, verbose_name="Дополнительная услуга")
    parent_service = models.ManyToManyField(
        'self', symmetrical=False, blank=True,
        related_name='additional_services'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"
        ordering = ['-created_at']

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
    services = models.ManyToManyField(Service, blank=True, related_name='leads')
    master = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name="leads")
    date_time = models.DateTimeField(null=True, blank=True)
    prepayment = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_url = models.URLField(verbose_name="Ссылка на оплату", blank=True, null=True)
    is_confirmed = models.BooleanField(default=None, null=True, blank=True)
    prepayment_paid = models.BooleanField(
        default=False,
        verbose_name="Предоплата получена"
    )
    date = models.DateField(null=True, blank=True)
    reminder_minutes = models.IntegerField(choices=REMINDER_CHOICES, default=60, verbose_name="Время напоминания")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Лид"
        verbose_name_plural = "Лиды"
        ordering = ['-created_at']
    
    def __str__(self):
        client_info = self.client.name if self.client else self.client_name or self.phone or "Без имени"
        services = ", ".join(service.name for service in self.services.all())
        master_name = self.master.first_name or self.master.email
        date = self.date_time.strftime("%d.%m.%Y %H:%M") if self.date_time else self.date.strftime("%d.%m.%Y") if self.date else "Нет даты"

        return f"{client_info} - {services} у {master_name} ({date})"

    def save(self, *args, **kwargs):
        if not self.client and self.phone:
            client, _ = Client.objects.get_or_create(
                phone=self.phone,
                defaults={'name': self.client_name or "Неизвестный"}
            )
            self.client = client

        super().save(*args, **kwargs)
