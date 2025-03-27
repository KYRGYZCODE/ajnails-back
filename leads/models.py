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
    master = models.ForeignKey(User, on_delete=models.CASCADE, related_name="leads")
    date_time = models.DateTimeField()
    prepayment = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_confirmed = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Лид"
        verbose_name_plural = "Лиды"

    def clean(self):
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
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.client_name} - {self.service} - {self.date_time}"
