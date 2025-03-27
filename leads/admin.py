from django.contrib import admin
from .models import Service, Lead

admin.site.register([Service, Lead])