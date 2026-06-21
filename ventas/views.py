from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.contrib.admin.views.decorators import staff_member_required
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from .models import Venta, Cuota
from django.contrib.auth.decorators import login_required
from django.utils import timezone

@login_required
def panel_ventas(request):
    # ACCIÓN: Si el usuario quiere pagar una cuota desde la interfaz
    if request.method == 'POST' and 'pagar_cuota_id' in request.POST:
        cuota_id = request.POST.get('pagar_cuota_id')
        cuota = get_object_or_404(Cuota, id=cuota_id)
        
        # Marcamos la cuota como pagada
        cuota.estado = 'PAGADA'
        cuota.fecha_pago = timezone.now().date()
        cuota.save()
        
        # Verificamos si era la última cuota pendiente de esa venta
        venta = cuota.venta
        if not venta.cuotas.filter(estado='PENDIENTE').exists():
            venta.estado = 'PAGADA'
            venta.save()
            
        return redirect('panel_ventas')

    # DATOS PARA LA PANTALLA:
    ventas = Venta.objects.all().order_by('-fecha')
    # Traemos solo las cuotas que están pendientes para el sector de cobranzas
    cuotas_pendientes = Cuota.objects.filter(estado='PENDIENTE').order_by('fecha_vencimiento')
    
    context = {
        'ventas': ventas,
        'cuotas_pendientes': cuotas_pendientes
    }
    return render(request, 'ventas/panel.html', context)

@staff_member_required
def descargar_pdf_venta(request, venta_id):
    # Buscamos la venta
    venta = get_object_or_404(Venta, id=venta_id)
    
    # Creamos la respuesta HTTP tipo PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Recibo_Venta_{venta.id}.pdf"'
    
    # Configuramos el documento PDF
    doc = SimpleDocTemplate(response, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    
    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=22, textColor=colors.HexColor('#1A252C'), spaceAfter=12)
    normal_style = styles['Normal']
    bold_style = ParagraphStyle('BoldStyle', parent=styles['Normal'], fontName='Helvetica-Bold')
    
    # Encabezado
    story.append(Paragraph(f"COMPROBANTE DE VENTA #{venta.id}", title_style))
    story.append(Paragraph(f"<b>Fecha:</b> {venta.fecha.strftime('%d/%m/%Y %H:%M')}", normal_style))
    cliente_nombre = venta.cliente.nombre if venta.cliente else "Consumidor Final"
    story.append(Paragraph(f"<b>Cliente:</b> {cliente_nombre}", normal_style))
    story.append(Paragraph(f"<b>Condición:</b> {venta.get_condicion_display()}", normal_style))
    story.append(Spacer(1, 20))
    
    # Tabla de Productos (Detalle)
    story.append(Paragraph("<b>DETALLE DE PRODUCTOS</b>", bold_style))
    story.append(Spacer(1, 8))
    
    data_productos = [['Producto', 'Cantidad', 'Precio Unit.', 'Subtotal']]
    for item in venta.items.all():
        subtotal = item.cantidad * item.precio_unitario
        data_productos.append([
            item.producto.nombre,
            str(item.cantidad),
            f"${item.precio_unitario}",
            f"${subtotal}"
        ])
    
    tabla_prod = Table(data_productos, colWidths=[250, 60, 100, 100])
    tabla_prod.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2C3E50')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#F8F9FA')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
    ]))
    story.append(tabla_prod)
    story.append(Spacer(1, 15))
    
    # Si es en cuotas, agregamos el detalle del plan de pago
    if venta.condicion == 'CUOTAS' and venta.cuotas.exists():
        story.append(Paragraph("<b>CRONOGRAMA DE CUOTAS</b>", bold_style))
        story.append(Spacer(1, 8))
        
        data_cuotas = [['Nro', 'Monto', 'Vencimiento', 'Estado']]
        for cuota in venta.cuotas.all():
            data_cuotas.append([
                f"Cuota {cuota.numero_cuota}",
                f"${cuota.monto}",
                cuota.fecha_vencimiento.strftime('%d/%m/%Y'),
                cuota.estado
            ])
        
        tabla_cuo = Table(data_cuotas, colWidths=[80, 100, 120, 100])
        tabla_cuo.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#7F8C8D')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ]))
        story.append(tabla_cuo)
        story.append(Spacer(1, 20))
        
    # TOTAL GENERAL
    story.append(Paragraph(f"<b>TOTAL A PAGAR: ${venta.total}</b>", title_style))
    
    # Construimos el PDF
    doc.build(story)
    return response