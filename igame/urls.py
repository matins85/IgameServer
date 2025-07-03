from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from accounts import views

from drf_spectacular.views import (
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    # Swagger api documentation
    path("swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    # Swagger redoc api documentation
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # index page
    path('', views.index, name="index"),
    # Admin
    path('admin/', admin.site.urls),
    # Accounts
    path('user/', include('accounts.urls')),
]
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
