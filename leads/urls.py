from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ServiceViewSet, LeadViewSet

router = DefaultRouter()
router.register(r'services', ServiceViewSet, basename='service')
router.register(r'leads', LeadViewSet, basename='lead')

urlpatterns = [
    path('', include(router.urls)),
]
