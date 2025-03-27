from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ServiceViewSet, LeadViewSet, ClientViewSet

router = DefaultRouter()
router.register(r'services', ServiceViewSet, basename='service')
router.register(r'leads', LeadViewSet, basename='lead')
router.register('clients', ClientViewSet, basename='client')

urlpatterns = [
    path('', include(router.urls)),
]
