import uuid 
from datetime import time
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager

from leads.models import Service

ROLE_CHOICES = (
        ('manager', 'Manager'),
        ('worker', 'Worker'),
        ('director', 'Director'),
    )

RIGHTS_CHOICES = (
        ('read', 'Чтение'),
        ('write', 'Запись'),
        ('admin', 'Администратор'),
    )

GENDER_CHOICES = (
    ('male', 'Male'),
    ('female', 'Female')
)

WEEKDAY_RUSSIAN = {
    1: 'Понедельник',
    2: 'Вторник',
    3: 'Среда',
    4: 'Четверг',
    5: 'Пятница',
    6: 'Суббота',
    7: 'Воскресенье'
}


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email должен быть указан')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Суперпользователь должен иметь is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Суперпользователь должен иметь is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, verbose_name="Электронная почта")
    phone_number = models.CharField(max_length=50, null=True, blank=True, verbose_name="Номер телефона")
    avatar = models.ImageField(upload_to='users/', null=True, blank=True, verbose_name='Аватарка')
    date_joined = models.DateTimeField(auto_now_add=True, verbose_name="Дата регистрации")
    date_of_birth = models.DateField(null=True, blank=True, verbose_name="Дата рождения")
    first_name = models.CharField(max_length=120, verbose_name="Имя", default='Имя')
    last_name = models.CharField(max_length=120, verbose_name="Фамилия", default='Фамилия')
    surname = models.CharField(max_length=120, null=True, blank=True, verbose_name="Отчество")
    gender = models.CharField(max_length=6, choices=GENDER_CHOICES, null=True, blank=True, verbose_name="Пол")
    about = models.CharField(max_length=300, null=True, blank=True)

    citizenship = models.CharField(max_length=100, null=True, blank=True, verbose_name="Гражданство")
    role = models.CharField(max_length=8, choices=ROLE_CHOICES, default='worker', verbose_name="Роль")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_fired = models.BooleanField(default=False, verbose_name="Уволен")
    termination_reason = models.TextField(null=True, blank=True, verbose_name="Основание увольнения")
    termination_order_date = models.DateField(null=True, blank=True, verbose_name="Дата приказа увольнения")
    termination_date = models.DateField(null=True, blank=True, verbose_name="Дата увольнения")

    is_employee = models.BooleanField(default=False, verbose_name="Является мастером")
    schedule_start = models.TimeField(default=time(9, 0))
    schedule_end = models.TimeField(default=time(18, 0))
    services = models.ManyToManyField(Service, blank=True, related_name="masters", verbose_name="Предоставляемые услуги")
    objects = CustomUserManager()

    USERNAME_FIELD = 'email'

    def fire(self, reason=None, order_date=None, termination_date=None):
        self.is_fired = True
        self.is_active = False
        self.termination_reason = reason
        self.termination_order_date = order_date
        self.termination_date = termination_date
        self.save()

    def restore(self):
        self.is_fired = False
        self.is_active = True
        self.termination_reason = None
        self.termination_order_date = None  
        self.termination_date = None
        self.save()

    def __str__(self):
        return f'{self.role} - {self.email}'

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"


class EmployeeSchedule(models.Model):
    WEEKDAY_CHOICES = (
        (1, 'monday'),
        (2, 'tuesday'),
        (3, 'wednesday'),
        (4, 'thursday'),
        (5, 'friday'),
        (6, 'saturday'),
        (7, 'sunday')
    )

    employee = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Работник', related_name='schedule')
    weekday = models.SmallIntegerField(choices=WEEKDAY_CHOICES, verbose_name='День недели')
    start_time = models.TimeField(verbose_name='Начало рабочего дня')
    end_time = models.TimeField(verbose_name='Конец рабочего дня')

    def __str__(self):
        return f'{self.employee.email} | {self.get_weekday_display()} {self.start_time} - {self.end_time}'
    
    class Meta:
        verbose_name = 'Рабочий день'
        verbose_name_plural = 'Расписания сотрудников'
        ordering = ['weekday']
