from rest_framework.routers import SimpleRouter
from django.urls import path, include
from .views import CustomTokenObtainPairView, CustomTokenRefreshView, RegisterView, UserViewSet, MeView

router = SimpleRouter()
router.register('users', UserViewSet)

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('auth/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('users/me/', MeView.as_view()),
    path('', include(router.urls)),
]