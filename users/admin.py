from django.contrib import admin
from .models import User, EmployeeSchedule

admin.site.register((User, EmployeeSchedule))