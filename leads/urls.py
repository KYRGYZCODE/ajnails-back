from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AverageBookingsReportView, FinancialReportView, NewClientsReportView, ServiceViewSet, LeadViewSet, ClientViewSet, LeadConfirmationViewSet, LeadsApprovalStatsReportView

router = DefaultRouter()
router.register(r'services', ServiceViewSet, basename='service')
router.register(r'leads', LeadViewSet, basename='lead')
router.register('clients', ClientViewSet, basename='client')
router.register('pendings', LeadConfirmationViewSet, basename='pending-confirmation')

urlpatterns = [
    path('', include(router.urls)),
    path('reports/financial-report/', FinancialReportView.as_view(), name='financial_report'),
    path('reports/new-clients-report/', NewClientsReportView.as_view(), name='new_clients_report'),
    path('reports/average-bookings-report/', AverageBookingsReportView.as_view(), name='average_bookings_report'),
    path('reports/leads-approval-report/', LeadsApprovalStatsReportView.as_view(), name='leads_approval_report')


]
