from django.core.management.base import BaseCommand
from users.models import User, EmployeeSchedule
from leads.models import Client, Service, Lead
from datetime import datetime, timedelta, time
import random

class Command(BaseCommand):
    help = 'Генерация тестовых данных: мастера, клиенты, услуги, лиды'

    def handle(self, *args, **kwargs):
        self.stdout.write("🚀 Начинается генерация данных...")

        User.objects.filter(email__startswith="master").delete()
        Client.objects.filter(phone__startswith="+7999").delete()
        Lead.objects.all().delete()

        masters = []
        for i in range(3):
            user, _ = User.objects.get_or_create(
                email=f"master{i}@test.com",
                defaults={
                    "first_name": f"Мастер{i}",
                    "last_name": "Тестов",
                    "is_employee": True,
                    "role": "worker",
                    "is_staff": True,
                    "is_active": True
                }
            )
            masters.append(user)

        clients = []
        for i in range(10):
            client, _ = Client.objects.get_or_create(
                phone=f"+799900000{i}",
                defaults={"name": f"Клиент {i}"}
            )
            clients.append(client)

        services = []
        for i in range(3):
            service, _ = Service.objects.get_or_create(
                name=f"Услуга {i}",
                defaults={
                    "duration": random.choice([30, 45, 60]),
                    "price": random.randint(500, 1500),
                    "is_long": False
                }
            )
            services.append(service)

        for master in masters:
            master.services.set(random.sample(services, k=2))
            for weekday in range(1, 6):
                EmployeeSchedule.objects.get_or_create(
                    employee=master,
                    weekday=weekday,
                    defaults={"start_time": time(9, 0), "end_time": time(18, 0)}
                )

        start_date = datetime(2025, 2, 1)
        end_date = datetime(2025, 5, 31)
        current_date = start_date
        lead_count = 0

        while current_date <= end_date:
            if current_date.weekday() < 5:
                for _ in range(random.randint(2, 4)):
                    master = random.choice(masters)
                    service = random.choice(list(master.services.all()))
                    client = random.choice(clients)
                    hour = random.randint(9, 16)
                    minute = random.choice([0, 30])
                    appointment_time = datetime.combine(current_date, time(hour, minute))

                    try:
                        Lead.objects.create(
                            client=client,
                            service=service,
                            master=master,
                            date_time=appointment_time,
                            prepayment=random.choice([0, 100, 200]),
                            reminder_minutes=60
                        )
                        lead_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"⚠️ Ошибка лида: {e}"))
            current_date += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(f"✅ Создано {lead_count} лидов"))
