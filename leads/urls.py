from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ServiceViewSet, LeadViewSet, ClientViewSet, LeadConfirmationViewSet

router = DefaultRouter()
router.register(r'services', ServiceViewSet, basename='service')
router.register(r'leads', LeadViewSet, basename='lead')
router.register('clients', ClientViewSet, basename='client')
router.register('pendings', LeadConfirmationViewSet, basename='pending-confirmation')

urlpatterns = [
    path('', include(router.urls)),
]
