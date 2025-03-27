from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

from drf_yasg import openapi
from drf_yasg.views import get_schema_view


schema_view = get_schema_view(
        openapi.Info(
            title="QStorage CRM Bantik Swagger",
            default_version='v1',
            description="QStorage",
            terms_of_service="https://media.tenor.com/Gu5-B9DztO4AAAAe/no-buff-richard.png",
            contact=openapi.Contact(email="no@mail.no"),
            license=openapi.License(name="no"),
        ),
        public=True,
    )

urlpatterns = [
    path('admin/', admin.site.urls),
    path('swagger/', schema_view.with_ui('swagger',
        cache_timeout=0), name='schema-swagger-ui'),
    path('', include('users.urls')),
    path('', include('leads.urls'))
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)