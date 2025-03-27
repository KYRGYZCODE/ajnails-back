from django.contrib import admin
from .models import Service, Lead, Client

admin.site.register([Service, Lead, Client])