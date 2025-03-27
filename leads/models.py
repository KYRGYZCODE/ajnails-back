from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings

User = settings.AUTH_USER_MODEL

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
    client_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    master = models.ForeignKey(User, on_delete=models.CASCADE)
    date_time = models.DateTimeField()
    prepayment = models.DecimalField(max_digits=10, decimal_places=2, default=0)


class Appointment(models.Model):
    client_name = models.CharField(max_length=255, verbose_name="Имя клиента")
    client_phone = models.CharField(max_length=50, verbose_name="Номер телефона клиента")
    
    master = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Мастер",
        limit_choices_to={"is_employee": True},
    )
    service = models.ForeignKey(
        "Service",
        on_delete=models.CASCADE,
        related_name="appointments",
        verbose_name="Услуга"
    )
    date_time = models.DateTimeField(verbose_name="Дата и время")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата и время создания")

    class Meta:
        unique_together = ("master", "date_time")
        verbose_name = 'Запись'
        verbose_name_plural = 'Записи'

    def clean(self):
        if self.service not in self.master.services.all():
            raise ValidationError(f"Мастер {self.master} не предоставляет услугу '{self.service}'.")

        if Appointment.objects.exclude(id=self.id).filter(master=self.master, date_time=self.date_time).exists():
            raise ValidationError("Этот мастер уже занят на выбранное время.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    
    def __str__(self):
        return f"{self.date_time} - {self.client_name}, мастер: {self.master.first_name}"
