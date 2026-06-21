# ventas/models.py
from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.db.models.signals import post_save
from django.dispatch import receiver

class Cliente(models.Model):
    nombre = models.CharField(max_length=150)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    nombre = models.CharField(max_length=150)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2) 
    stock = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.nombre} (${self.precio_venta}) - Stock: {self.stock}"


class Venta(models.Model):
    CONDICION_CHOICES = [
        ('CONTADO', 'Contado'),
        ('CUOTAS', 'Crédito / Cuotas'),
    ]
    ESTADO_CHOICES = [
        ('PAGADA', 'Pagada Totalmente'),
        ('PENDIENTE', 'Pendiente de Pago'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True)
    fecha = models.DateTimeField(default=timezone.now)
    condicion = models.CharField(max_length=10, choices=CONDICION_CHOICES, default='CONTADO')
    cant_cuotas_pactadas = models.IntegerField(default=1, verbose_name="Cantidad de cuotas")
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='PENDIENTE')

    def __str__(self):
        return f"Venta #{self.id} - {self.cliente if self.cliente else 'Consumidor Final'}"

    # Eliminamos la creación automática de cuotas de aquí porque ahora se disparará 
    # desde las señales una vez que conozcamos el TOTAL REAL de la venta.
    def cuotas_restantes(self):
        if self.condicion == 'CONTADO':
            return 0
        return self.cuotas.filter(estado='PENDIENTE').count()


class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.IntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, blank=True)

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre}"

    # Si no escribes el precio unitario a mano, Django toma automáticamente el precio actual del producto
    def save(self, *args, **kwargs):
        if not self.precio_unitario:
            self.precio_unitario = self.producto.precio_venta
        super().save(*args, **kwargs)


class Cuota(models.Model):
    ESTADO_CUOTA = [
        ('PENDIENTE', 'Pendiente'),
        ('PAGADA', 'Pagada'),
    ]
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='cuotas')
    numero_cuota = models.IntegerField()
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_vencimiento = models.DateField()
    estado = models.CharField(max_length=10, choices=ESTADO_CUOTA, default='PENDIENTE')
    
    fecha_pago = models.DateField(blank=True, null=True)

    def __str__(self):
        cliente_nombre = self.venta.cliente.nombre if self.venta.cliente else "Consumidor Final"
        return f"Venta #{self.venta.id} - {cliente_nombre} - Cuota {self.numero_cuota}/{self.venta.cant_cuotas_pactadas}"


# ==================== SEÑALES (SIGNALS) ====================

@receiver(post_save, sender=DetalleVenta)
def procesar_detalle_venta(sender, instance, created, **kwargs):
    """
    Cada vez que se agrega un producto al detalle:
    1. Resta el stock (si el detalle es nuevo).
    2. Recalcula el total de la venta sumando todos sus detalles.
    3. Si es en cuotas y es el primer producto que define el total, genera las cuotas.
    """
    venta = instance.venta

    # 1. Restar Stock
    if created:
        producto = instance.producto
        producto.stock -= instance.cantidad
        producto.save()

    # 2. Recalcular el Total de la Venta
    total_calculado = sum(item.cantidad * item.precio_unitario for item in venta.items.all())
    venta.total = total_calculado
    venta.save()

    # 3. Generar Cuotas Automáticas con el total real (solo si no se crearon antes)
    if venta.condicion == 'CUOTAS' and venta.cant_cuotas_pactadas > 1 and not venta.cuotas.exists():
        monto_cuota = venta.total / venta.cant_cuotas_pactadas
        for i in range(1, venta.cant_cuotas_pactadas + 1):
            fecha_vencimiento = venta.fecha.date() + timedelta(days=30 * i)
            Cuota.objects.create(
                venta=venta,
                numero_cuota=i,
                monto=monto_cuota,
                fecha_vencimiento=fecha_vencimiento
            )