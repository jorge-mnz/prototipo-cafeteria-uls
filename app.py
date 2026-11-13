import streamlit as st
import random
import string
import pandas as pd
import io
import os
import qrcode
from datetime import datetime

# Configuración de página
st.set_page_config(page_title="Domeyko GO - Casino ULS", page_icon="🍔", layout="wide")

# ==========================================
# PARÁMETROS DEL SISTEMA
# ==========================================
CLAVE_PERSONAL = "domeyko2026"  # Contraseña para acceder al KDS y Métricas
LIMIT_PER_SLOT = 10             # Máximo 10 pedidos activos por franja
TIME_SLOTS = [
    "13:00 - 13:15",
    "13:15 - 13:30",
    "13:30 - 13:45",
    "13:45 - 14:00"
]

if "db_orders" not in st.session_state:
    st.session_state.db_orders = []

if "mis_pedidos" not in st.session_state:
    st.session_state.mis_pedidos = []

if "personal_autenticado" not in st.session_state:
    st.session_state.personal_autenticado = False

MENU = {
    "Almuerzo Completo": {
        "precio": 2650,
        "baes": True,
        "solo_baes": False,
        "desc": "Plato de fondo, ensalada, pan y postre"
    },
    "Menú BAES": {
        "precio": 2350,
        "baes": True,
        "solo_baes": True,
        "desc": "Menú convenio exclusivo pago con tarjeta BAES / JUNAEB"
    },
    "Colación": {
        "precio": 2000,
        "baes": False,
        "solo_baes": False,
        "desc": "Plato de fondo y pan (No apto BAES)"
    },
    "Sándwich": {
        "precio": 1800,
        "baes": True,
        "solo_baes": False,
        "desc": "Sándwich preparado del día"
    }
}

ESTADOS_PEDIDO = ["Recibido", "En preparación", "Listo", "Entregado"]

def formato_clp(valor: int) -> str:
    return f"${valor:,}".replace(",", ".")

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

def mostrar_tarjeta_seguimiento(pedido: dict):
    progreso_map = {
        "Recibido": 25,
        "En preparación": 50,
        "Listo": 85,
        "Entregado": 100
    }
    estado = pedido["estado"]
    with st.container(border=True):
        col_info, col_qr = st.columns([3, 1])
        with col_info:
            st.markdown(f"#### 🧾 Pedido `{pedido['id']}` — {pedido['producto']}")
            st.write(f"**Franja de retiro:** {pedido['franja']} | **Pago:** {pedido['pago']} ({formato_clp(pedido['precio'])})")
            st.progress(progreso_map.get(estado, 25))
            if estado == "Recibido":
                st.info("🕒 Estado: **Recibido** (En cola de preparación)")
            elif estado == "En preparación":
                st.warning("👨‍🍳 Estado: **En preparación** (Tu pedido se está armando)")
            elif estado == "Listo":
                st.success("✅ Estado: **¡LISTO PARA RETIRAR!** Acércate al mesón de entrega.")
            elif estado == "Entregado":
                st.write(f"✔️ Estado: **Entregado** (Retirado a las {pedido['hora_entrega']})")
        with col_qr:
            qr_bytes = generar_qr_image(f"PEDIDO:{pedido['id']}|FRANJA:{pedido['franja']}")
            st.image(qr_bytes, caption=pedido["id"], width=120)

def verificar_login_personal() -> bool:
    if st.session_state.personal_autenticado:
        return True

    st.title("🔒 Acceso Restringido - Personal Cafetería")
    st.markdown("Ingresa la clave operativa para gestionar pedidos y métricas.")
    with st.form("form_login_personal"):
        clave_ingresada = st.text_input("Contraseña:", type="password")
        submit = st.form_submit_button("Ingresar", type="primary")
        if submit:
            if clave_ingresada == CLAVE_PERSONAL:
                st.session_state.personal_autenticado = True
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta.")
    return False

# ==========================================
# BARRA LATERAL Y LOGO
# ==========================================
if os.path.exists("logo.jpeg"):
    st.sidebar.image("logo.jpeg", use_container_width=True)

st.sidebar.title("📌 Menú de Navegación")
modo = st.sidebar.radio("Selecciona la vista:", [
    "📱 Estudiante (Realizar Pedido)", 
    "🍳 Personal Cafetería (KDS)",
    "📊 Panel de Métricas / Exportación"
])

if st.session_state.personal_autenticado:
    st.sidebar.markdown("---")
    st.sidebar.success("🔓 Sesión de personal activa")
    if st.sidebar.button("Cerrar sesión"):
        st.session_state.personal_autenticado = False
        st.rerun()

# ==========================================
# VISTA 1: ESTUDIANTE
# ==========================================
if modo == "📱 Estudiante (Realizar Pedido)":
    if os.path.exists("logo.jpeg"):
        st.image("logo.jpeg", width=360)
    else:
        st.title("🍔 Domeyko GO - Casino ULS")

    st.subheader("Sistema de Pedidos Anticipados por QR")

    # Seguimiento directo en pantalla si el usuario ya realizó pedidos en esta sesión
    if st.session_state.mis_pedidos:
        col_titulo, col_btn = st.columns([4, 1])
        with col_titulo:
            st.markdown("### 📍 Seguimiento en Vivo de tu Pedido")
        with col_btn:
            if st.button("🔄 Actualizar"):
                st.rerun()

        for pid in reversed(st.session_state.mis_pedidos):
            pedido_actual = next((o for o in st.session_state.db_orders if o["id"] == pid), None)
            if pedido_actual:
                mostrar_tarjeta_seguimiento(pedido_actual)
        st.markdown("---")

    # Formulario de nuevo pedido
    st.markdown("### 🛍️ Realizar Nuevo Pedido")
    st.markdown("**1. Selecciona tu Producto**")
    producto_sel = st.radio(
        "Opciones disponibles:",
        options=list(MENU.keys()),
        format_func=lambda x: f"{x} - {formato_clp(MENU[x]['precio'])} ({MENU[x]['desc']})"
    )

    st.markdown("**2. Selecciona la Franja Horaria de Retiro**")
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

    st.markdown("**3. Medio de Pago**")
    if MENU[producto_sel]["solo_baes"]:
        metodos_pago = ["BAES / JUNAEB"]
        st.info("💳 Este menú es exclusivo para pago con tarjeta BAES / JUNAEB.")
    else:
        metodos_pago = ["Débito / Crédito", "Efectivo en Caja"]
        if MENU[producto_sel]["baes"]:
            metodos_pago.append("BAES / JUNAEB")
        else:
            st.warning("⚠️ Nota: El producto 'Colación' no admite pago con tarjeta BAES/JUNAEB.")

    pago_sel = st.selectbox("Selecciona tu medio de pago:", metodos_pago)

    total = MENU[producto_sel]["precio"]
    st.write(f"**Total a Pagar:** {formato_clp(total)}")

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
            st.session_state.mis_pedidos.append(order_id)
            st.rerun()

    # Buscador secundario por si se consulta desde otro navegador o dispositivo
    with st.expander("🔍 Consultar otro pedido por código"):
        busqueda_id = st.text_input("Ingresa el código de pedido (ej. ORD-1234):").strip().upper()
        if busqueda_id:
            pedido_encontrado = next((o for o in st.session_state.db_orders if o["id"] == busqueda_id), None)
            if pedido_encontrado:
                mostrar_tarjeta_seguimiento(pedido_encontrado)
            else:
                st.error("Código de pedido no encontrado.")

# ==========================================
# VISTA 2: PERSONAL CAFETERÍA (KDS)
# ==========================================
elif modo == "🍳 Personal Cafetería (KDS)":
    if not verificar_login_personal():
        st.stop()

    # CSS para que el botón primary ("Entregado") sea verde destacado en el KDS
    st.markdown("""
        <style>
        div.stButton > button[kind="primary"] {
            background-color: #28a745;
            border-color: #28a745;
            color: white;
            font-weight: bold;
        }
        div.stButton > button[kind="primary"]:hover {
            background-color: #218838;
            border-color: #1e7e34;
            color: white;
        }
        div.stButton > button[kind="primary"]:disabled {
            background-color: #1e7e34;
            border-color: #1e7e34;
            color: #e2e8f0;
            opacity: 0.75;
        }
        </style>
    """, unsafe_allow_html=True)

    st.title("🍳 Pantalla de Control - Personal de Cafetería")
    
    if not st.session_state.db_orders:
        st.info("No hay pedidos registrados en el sistema.")
    else:
        pedidos_activos = [o for o in st.session_state.db_orders if o["estado"] != "Entregado"]
        st.metric("Pedidos Pendientes / En Proceso", len(pedidos_activos))

        for order in st.session_state.db_orders:
            with st.expander(
                f"📦 Pedido {order['id']} | {order['franja']} | {order['producto']} — Estado actual: {order['estado'].upper()}",
                expanded=(order['estado'] != 'Entregado')
            ):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Producto:** {order['producto']}")
                    st.write(f"**Hora Pedido:** {order['hora_registro']}")
                with col2:
                    st.write(f"**Pago:** {order['pago']}")
                    st.write(f"**Transacción:** `{order['tx_id']}`")

                st.markdown("**Actualizar estado del pedido:**")
                b1, b2, b3, b4 = st.columns(4)
                botones_config = [
                    (b1, "Recibido", "📥 Recibido", "secondary"),
                    (b2, "En preparación", "👨‍🍳 En preparación", "secondary"),
                    (b3, "Listo", "🔔 Listo", "secondary"),
                    (b4, "Entregado", "✅ Entregado", "primary"),
                ]

                for col_btn, estado_obj, etiqueta, tipo_btn in botones_config:
                    with col_btn:
                        es_actual = (order["estado"] == estado_obj)
                        texto_btn = f"• {etiqueta} •" if es_actual else etiqueta
                        if st.button(
                            texto_btn,
                            key=f"btn_{order['id']}_{estado_obj}",
                            type=tipo_btn,
                            disabled=es_actual,
                            use_container_width=True
                        ):
                            order["estado"] = estado_obj
                            if estado_obj == "Entregado":
                                order["hora_entrega"] = datetime.now().strftime("%H:%M:%S")
                            else:
                                order["hora_entrega"] = "-"
                            st.rerun()

# ==========================================
# VISTA 3: MÉTRICAS Y EXPORTACIÓN
# ==========================================
else:
    if not verificar_login_personal():
        st.stop()

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