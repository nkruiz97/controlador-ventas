# ventas/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.panel_ventas, name='panel_ventas'),
    path('venta/<int:venta_id>/pdf/', views.descargar_pdf_venta, name='descargar_pdf_venta'),
]