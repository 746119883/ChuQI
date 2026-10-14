from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api_views

router = DefaultRouter()
router.register(r'health/checkups', api_views.CheckupPlanViewSet, basename='checkup')
router.register(r'health/attachments', api_views.HealthAttachmentViewSet, basename='health-attachment')
router.register(r'health/vaccines', api_views.VaccinePlanViewSet, basename='vaccine')
router.register(r'health/visits', api_views.MedicalVisitViewSet, basename='visit')

urlpatterns = [
    path('health/profiles/', api_views.HealthProfileListView.as_view(), name='health-profiles'),
    path('health/profiles/<int:user_id>/', api_views.HealthProfileDetailView.as_view(), name='health-profile-detail'),
    path('health/metrics-history/', api_views.MetricsHistoryView.as_view(), name='health-metrics-history'),
    path('health/reminder-settings/', api_views.HealthReminderSettingsView.as_view(), name='health-reminder-settings'),
    path('', include(router.urls)),
]
