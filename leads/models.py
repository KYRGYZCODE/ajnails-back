import re
from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings

User = settings.AUTH_USER_MODEL

class Client(models.Model):
    phone = models.CharField(max_length=20, unique=True, verbose_name="Номер телефона")
    name = models.CharField(max_length=255, verbose_name="Имя клиента")

    class Meta:
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"

    def __str__(self):
        return f"{self.name} ({self.phone})"


class Service(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="Название услуги")
    duration = models.IntegerField(verbose_name="Длительность (мин)", default=30)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=500)

    class Meta:
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"

    def __str__(self):
        return self.name


class Lead(models.Model):
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Клиент")
    client_name = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    master = models.ForeignKey(User, on_delete=models.CASCADE, related_name="leads")
    date_time = models.DateTimeField()
    prepayment = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_confirmed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Лид"
        verbose_name_plural = "Лиды"

    def clean(self):
        if not self.pk:
            if self.phone:
                if not re.match(r'^\d{9}$', self.phone):
                    raise ValidationError("Номер телефона должен состоять из 9 цифр (например, 550990123).")

            if not self.client and not self.phone:
                raise ValidationError("Должен быть указан либо клиент, либо номер телефона.")

            if Lead.objects.filter(
                date_time=self.date_time,
                service=self.service,
                master=self.master
            ).exists():
                raise ValidationError("У этого мастера уже есть запись на указанное время для данной услуги.")

            if not self.master.services.filter(id=self.service.id).exists():
                raise ValidationError("Этот мастер не оказывает данную услугу.")

    def save(self, *args, **kwargs):
        self.clean()

        if not self.client:
            client, created = Client.objects.get_or_create(
                phone=self.phone,
                defaults={'name': self.client_name or "Неизвестный"}
            )
            self.client = client

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.client.name if self.client else self.client_name} - {self.service} - {self.date_time}"