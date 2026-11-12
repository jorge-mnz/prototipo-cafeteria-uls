import streamlit as st
import random
import string
import pandas as pd
import io
import qrcode
from datetime import datetime

# Configuración de página
st.set_page_config(page_title="Cafetería ULS - Pedidos QR", page_icon="🍔", layout="wide")

# ==========================================
# PARÁMETROS ACTUALIZADOS
# ==========================================
LIMIT_PER_SLOT = 10  # Máximo 10 pedidos activos por franja
TIME_SLOTS = [
    "13:00 - 13:15",
    "13:15 - 13:30",
    "13:30 - 13:45",
    "13:45 - 14:00"
]

if "db_orders" not in st.session_state:
    st.session_state.db_orders = []

MENU = {
    "Almuerzo Completo": {"precio": 3500, "baes": True, "desc": "Plato de fondo, ensalada, pan y postre"},
    "Colación": {"precio": 2800, "baes": False, "desc": "Plato de fondo y pan (No apto BAES)"},
    "Sándwich": {"precio": 1800, "baes": True, "desc": "Sándwich preparado del día"}
}

def procesar_pago(metodo: str, monto: int):
    if metodo in ["Débito / Crédito", "BAES / JUNAEB", "Efectivo en Caja"]:
        tx_id = "TX-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return True, tx_id
    return False, "Método no válido"

def generar_id_pedido():
    return "ORD-" + ''.join(random.choices(string.digits, k=4))

def contar_pedidos_franja(franja):
    return sum(1 for o in st.session_state.db_orders if o["franja"] == franja and o["estado"] != "Entregado")

def generar_qr_image(data_text):
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(data_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# Barra lateral
st.sidebar.title("📌 Menú de Navegación")
modo = st.sidebar.radio("Selecciona la vista:", [
    "📱 Estudiante (Realizar Pedido)", 
    "🍳 Personal Cafetería (KDS)",
    "📊 Panel de Métricas / Exportación"
])

# VISTA ESTUDIANTE
if modo == "📱 Estudiante (Realizar Pedido)":
    st.title("🍔 Cafetería Campus Ignacio Domeyko")
    st.subheader("Sistema de Pedidos Anticipados por QR")

    tab1, tab2 = st.tabs(["🛍️ Nuevo Pedido", "🔍 Consultar Estado de Pedido"])

    with tab1:
        st.markdown("### 1. Selecciona tu Producto")
        producto_sel = st.radio(
            "Opciones disponibles:",
            options=list(MENU.keys()),
            format_func=lambda x: f"{x} - ${MENU[x]['precio']:,} ({MENU[x]['desc']})"
        )

        st.markdown("---")
        st.markdown("### 2. Selecciona la Franja Horaria de Retiro")
        
        franjas_disponibles = []
        for slot in TIME_SLOTS:
            ocupados = contar_pedidos_franja(slot)
            if ocupados < LIMIT_PER_SLOT:
                franjas_disponibles.append(f"{slot} ({LIMIT_PER_SLOT - ocupados} cupos disponibles)")
            else:
                franjas_disponibles.append(f"{slot} (AGOTADO)")

        franja_sel_raw = st.selectbox("Franjas de retiro disponibles:", franjas_disponibles)
        
        if "AGOTADO" in franja_sel_raw:
            st.error("⚠️ La franja seleccionada está totalmente agotada. Por favor elige otra.")
            st.stop()

        franja_sel = franja_sel_raw.split(" (")[0]

        st.markdown("---")
        st.markdown("### 3. Medio de Pago")
        
        metodos_pago = ["Débito / Crédito", "Efectivo en Caja"]
        if MENU[producto_sel]["baes"]:
            metodos_pago.append("BAES / JUNAEB")
        else:
            st.warning("⚠️ Nota: El producto 'Colación' no admite pago con tarjeta BAES/JUNAEB.")

        pago_sel = st.selectbox("Selecciona tu medio de pago:", metodos_pago)

        st.markdown("---")
        total = MENU[producto_sel]["precio"]
        st.write(f"**Total a Pagar:** ${total:,}")

        if st.button("Confirmar y Pagar Pedido", type="primary"):
            exito, tx_id = procesar_pago(pago_sel, total)
            if exito:
                order_id = generar_id_pedido()
                hora_actual = datetime.now().strftime("%H:%M:%S")
                nuevo_pedido = {
                    "id": order_id,
                    "producto": producto_sel,
                    "precio": total,
                    "franja": franja_sel,
                    "pago": pago_sel,
                    "tx_id": tx_id,
                    "estado": "Recibido",
                    "hora_registro": hora_actual,
                    "hora_entrega": "-"
                }
                st.session_state.db_orders.append(nuevo_pedido)
                st.success(f"🎉 ¡Pedido registrado exitosamente! Tu código de retiro es: **{order_id}**")
                
                qr_bytes = generar_qr_image(f"PEDIDO:{order_id}|FRANJA:{franja_sel}")
                col_qr, col_info = st.columns([1, 3])
                with col_qr:
                    st.image(qr_bytes, caption=f"Comprobante {order_id}", width=150)
                with col_info:
                    st.info(f"Muestra este código QR o dicta tu identificador **{order_id}** al retirar en la franja **{franja_sel}**.")

    with tab2:
        st.markdown("### Estado de tu Pedido en Tiempo Real")
        busqueda_id = st.text_input("Ingresa tu código de pedido (ej. ORD-1234):").strip().upper()
        
        if busqueda_id:
            pedido_encontrado = next((o for o in st.session_state.db_orders if o["id"] == busqueda_id), None)
            if pedido_encontrado:
                st.write(f"**Producto:** {pedido_encontrado['producto']}")
                st.write(f"**Franja de Retiro:** {pedido_encontrado['franja']}")
                
                estado = pedido_encontrado["estado"]
                if estado == "Recibido":
                    st.info("🕒 Estado: **Recibido** (En espera de preparación)")
                elif estado == "En preparación":
                    st.warning("👨‍🍳 Estado: **En preparación** (Casi listo)")
                elif estado == "Listo":
                    st.success("✅ Estado: **¡LISTO PARA RETIRAR!** Dirígete al punto de entrega.")
                elif estado == "Entregado":
                    st.write("✔️ Estado: **Entregado**")
            else:
                st.error("Código de pedido no encontrado.")

# VISTA PERSONAL (KDS)
elif modo == "🍳 Personal Cafetería (KDS)":
    st.title("🍳 Pantalla de Control - Personal de Cafetería")
    
    if not st.session_state.db_orders:
        st.info("No hay pedidos registrados en el sistema.")
    else:
        pedidos_activos = [o for o in st.session_state.db_orders if o["estado"] != "Entregado"]
        st.metric("Pedidos Pendientes/En Proceso", len(pedidos_activos))

        for order in st.session_state.db_orders:
            with st.expander(f"📦 Pedido {order['id']} - {order['franja']} | Estado: {order['estado']}", expanded=(order['estado'] != 'Entregado')):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**Producto:** {order['producto']}")
                    st.write(f"**Hora Pedido:** {order['hora_registro']}")
                with col2:
                    st.write(f"**Pago:** {order['pago']}")
                    st.write(f"**Transacción:** `{order['tx_id']}`")
                with col3:
                    nuevo_estado = st.selectbox(
                        "Cambiar Estado:",
                        ["Recibido", "En preparación", "Listo", "Entregado"],
                        index=["Recibido", "En preparación", "Listo", "Entregado"].index(order["estado"]),
                        key=f"select_{order['id']}"
                    )
                    if nuevo_estado != order["estado"]:
                        order["estado"] = nuevo_estado
                        if nuevo_estado == "Entregado":
                            order["hora_entrega"] = datetime.now().strftime("%H:%M:%S")
                        st.rerun()

# VISTA MÉTRICAS Y EXPORTACIÓN
else:
    st.title("📊 Análisis de Datos y Trazabilidad del Prototipo")
    st.markdown("Registro cuantitativo de órdenes para validación de tiempos de atención.")

    if not st.session_state.db_orders:
        st.info("Aún no hay datos recolectados. Registra algunos pedidos desde la vista de estudiante.")
    else:
        df = pd.DataFrame(st.session_state.db_orders)
        st.dataframe(df, use_container_width=True)

        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar Reporte de Tiempos (CSV)",
            data=csv_data,
            file_name=f"reporte_cafeteria_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            type="primary"
        )