# ventas/urls.py
from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.panel_ventas, name='panel_ventas'),
    path('nueva/', views.crear_venta_ajax, name='crear_venta'),
    path('venta/<int:venta_id>/pdf/', views.descargar_pdf_venta, name='descargar_pdf_venta'),
    path('ventas/', include('ventas.urls')),
]