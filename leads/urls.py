from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import AverageBookingsReportView, FinancialReportView, NewClientsReportView, ServiceAvailableSlotsView, ServiceViewSet, LeadViewSet, ClientViewSet, LeadConfirmationViewSet, LeadsApprovalStatsReportView, ServiceMastersWithSlotsView, AvailableDatesView

router = SimpleRouter()
router.register(r'services', ServiceViewSet, basename='service')
router.register(r'leads', LeadViewSet, basename='lead')
router.register('clients', ClientViewSet, basename='client')
router.register('pendings', LeadConfirmationViewSet, basename='pending-confirmation')

urlpatterns = [
    path('services/available-slots/', ServiceAvailableSlotsView.as_view(), name='service-available-slots'),
    path('employees/available-slots/', ServiceMastersWithSlotsView.as_view(), name='employees-available-slots'),
    path('', include(router.urls)),
    path('reports/financial-report/', FinancialReportView.as_view(), name='financial_report'),
    path('reports/new-clients-report/', NewClientsReportView.as_view(), name='new_clients_report'),
    path('reports/average-bookings-report/', AverageBookingsReportView.as_view(), name='average_bookings_report'),
    path('reports/leads-approval-report/', LeadsApprovalStatsReportView.as_view(), name='leads_approval_report'),
    path('available-dates/', AvailableDatesView.as_view(), name='available-dates')


]
