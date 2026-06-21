from django.contrib import admin
from django.utils import timezone  # Para obtener la fecha actual al pagar
from django.utils.html import format_html  # Para renderizar el botón HTML del PDF
from django.urls import reverse  # <--- ¡ESTA ES LA LÍNEA QUE FALTA AGREGAR!
from .models import Cliente, Producto, Venta, DetalleVenta, Cuota

# 1. ESTOS SON LOS "INLINES" (Se muestran DENTRO de la pantalla de Venta)
class DetalleVentaInline(admin.TabularInline):
    model = DetalleVenta
    extra = 1

class CuotaInline(admin.TabularInline):
    model = Cuota
    extra = 0
    # Al ser inline dentro de venta, las dejamos de solo lectura para no romper la lógica
    readonly_fields = ('numero_cuota', 'monto', 'fecha_vencimiento')
    # Esto evita que puedas agregar cuotas a mano desde aquí
    can_delete = False


# 2. PANEL DE VENTAS
@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    # CAMBIO DE ORDEN: Pasamos 'bajar_pdf' al segundo lugar de la lista
    list_display = ('id', 'bajar_pdf', 'cliente', 'fecha', 'condicion', 'total', 'estado', 'cuotas_restantes')
    list_filter = ('condicion', 'estado', 'fecha')
    inlines = [DetalleVentaInline, CuotaInline]
    readonly_fields = ('total',)
    @admin.display(description='Comprobante')
    def bajar_pdf(self, obj):
        url = reverse('descargar_pdf_venta', args=[obj.id])
        # CORRECCIÓN: Quitamos el f-string interno y pasamos 'url' al final de format_html
        return format_html('<a class="button" href="{}" style="background-color: #2c3e50; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold; text-decoration: none;">PDF</a>', url)


# 3. PANEL DE CUOTAS INDEPENDIENTE (Aquí manejas la cobranza general)
@admin.register(Cuota)
class CuotaAdmin(admin.ModelAdmin):
    list_display = ('get_cliente', 'venta_link', 'numero_cuota', 'monto', 'fecha_vencimiento', 'estado', 'fecha_pago')
    list_filter = ('estado', 'fecha_vencimiento', 'venta__cliente')
    search_fields = ('venta__cliente__nombre', 'venta__id')
    
    actions = ['marcar_como_pagada']

    @admin.display(description='Cliente')
    def get_cliente(self, obj):
        return obj.venta.cliente.nombre if obj.venta.cliente else "Consumidor Final"

    @admin.display(description='Nro. Venta')
    def venta_link(self, obj):
        return f"Venta #{obj.venta.id}"

    def marcar_como_pagada(self, request, queryset):
        filas_actualizadas = queryset.update(estado='PAGADA', fecha_pago=timezone.now().date())
        
        for cuota in queryset:
            venta = cuota.venta
            if not venta.cuotas.filter(estado='PENDIENTE').exists():
                venta.estado = 'PAGADA'
                venta.save()

        self.message_user(request, f"Se actualizaron {filas_actualizadas} cuotas como pagadas con éxito.")


# 4. REGISTROS SIMPLES
admin.site.register(Cliente)
admin.site.register(Producto)