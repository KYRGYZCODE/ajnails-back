from django.contrib import admin
from .models import Service, Lead, Appointment

admin.site.register([Service, Lead, Appointment])