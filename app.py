import streamlit as st
import random
import string
import pandas as pd
import io
import os
import time
import qrcode
from datetime import datetime

# Configuración de página
st.set_page_config(page_title="Domeyko GO - Casino ULS", page_icon="🍔", layout="wide")

# ==========================================
# PARÁMETROS DEL SISTEMA
# ==========================================
CLAVE_PERSONAL = "domeyko2026"  # Contraseña para acceder al KDS y Métricas
LIMIT_PER_SLOT = 10             # Máximo 10 unidades/cupos por franja de 15 min
MAX_ITEMS_CARRITO = 3           # Máximo 3 productos por pedido
COOLDOWN_SEGUNDOS = 60          # Límite de 1 pedido por minuto por dispositivo

TIME_SLOTS = [
    "13:00 - 13:15",
    "13:15 - 13:30",
    "13:30 - 13:45",
    "13:45 - 14:00"
]

# Tasas de refresco optimizadas para conectividad universitaria (en segundos)
REFRESH_SEGUIMIENTO_ESTUDIANTE = 10
REFRESH_CUPOS_ESTUDIANTE = 15
REFRESH_KDS_OPERADOR = 6

# Base de datos compartida en la memoria del servidor
@st.cache_resource
def obtener_base_datos():
    return []

db_orders = obtener_base_datos()

# Estado local individual de cada celular/navegador
if "mis_pedidos" not in st.session_state:
    st.session_state.mis_pedidos = []

if "personal_autenticado" not in st.session_state:
    st.session_state.personal_autenticado = False

if "ultimo_pedido_ts" not in st.session_state:
    st.session_state.ultimo_pedido_ts = 0.0

if "pedido_popup" not in st.session_state:
    st.session_state.pedido_popup = None

MENU = {
    "Almuerzo Completo": {
        "precio": 2650,
        "baes": True,
        "solo_baes": False,
        "desc": "Plato de fondo, ensalada, pan y postre del día.",
        "img_local": "almuerzo.jpg",
        "img_fallback": "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=400&h=300&fit=crop"
    },
    "Menú BAES": {
        "precio": 2350,
        "baes": True,
        "solo_baes": True,
        "desc": "Menú convenio exclusivo pago con tarjeta BAES / JUNAEB.",
        "img_local": "baes.jpg",
        "img_fallback": "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=400&h=300&fit=crop"
    },
    "Colación": {
        "precio": 2000,
        "baes": False,
        "solo_baes": False,
        "desc": "Plato de fondo y pan (No apto para pago BAES).",
        "img_local": "colacion.jpg",
        "img_fallback": "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=400&h=300&fit=crop"
    },
    "Sándwich": {
        "precio": 1800,
        "baes": True,
        "solo_baes": False,
        "desc": "Sándwich preparado fresco del día.",
        "img_local": "sandwich.jpg",
        "img_fallback": "https://images.unsplash.com/photo-1528735602780-2552fd46c7af?w=400&h=300&fit=crop"
    }
}

if "carrito" not in st.session_state:
    st.session_state.carrito = {prod: 0 for prod in MENU.keys()}

# ==========================================
# FUNCIONES AUXILIARES
# ==========================================
def formato_clp(valor: int) -> str:
    return f"${valor:,}".replace(",", ".")

def procesar_pago(metodo: str, monto: int):
    if metodo in ["Débito / Crédito", "BAES / JUNAEB", "Efectivo en Caja"]:
        tx_id = "TX-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return True, tx_id
    return False, "Método no válido"

def generar_id_pedido():
    return "ORD-" + ''.join(random.choices(string.digits, k=4))

def contar_cupos_ocupados_franja(franja: str) -> int:
    # Cada unidad de producto ocupa 1 cupo en la franja (excepto pedidos descartados)
    return sum(
        o.get("cantidad_total", 1)
        for o in db_orders
        if o["franja"] == franja and o["estado"] != "Descartado"
    )

def obtener_imagen_producto(prod: str) -> str:
    ruta_local = MENU[prod]["img_local"]
    if os.path.exists(ruta_local):
        return ruta_local
    return MENU[prod]["img_fallback"]

@st.cache_data
def generar_qr_image(data_text: str):
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(data_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

@st.dialog("🎉 ¡Pedido Confirmado Exitosamente!")
def mostrar_popup_confirmacion(pedido: dict):
    st.success(f"Gracias **{pedido['cliente']}**, tu orden ya ingresó a cocina.")
    col_txt, col_qr = st.columns([2, 1])
    with col_txt:
        st.markdown(f"### Código: `{pedido['id']}`")
        st.write(f"**Franja de retiro:** {pedido['franja']}")
        st.write(f"**Detalle:** {pedido['detalle_productos']}")
        st.write(f"**Total pagado:** {formato_clp(pedido['precio'])} ({pedido['pago']})")
        st.info("Puedes cerrar esta ventana y revisar el avance en tiempo real más arriba.")
    with col_qr:
        qr_bytes = generar_qr_image(f"PEDIDO:{pedido['id']}|CLIENTE:{pedido['cliente']}|FRANJA:{pedido['franja']}")
        st.image(qr_bytes, caption=pedido["id"], width=130)

    if st.button("Entendido, ver seguimiento", type="primary", use_container_width=True):
        st.rerun()

def mostrar_tarjeta_seguimiento(pedido: dict):
    progreso_map = {
        "Recibido": 25,
        "En preparación": 50,
        "Listo": 85,
        "Entregado": 100,
        "Descartado": 0
    }
    estado = pedido["estado"]
    with st.container(border=True):
        col_info, col_qr = st.columns([3, 1])
        with col_info:
            st.markdown(f"#### 🧾 Pedido `{pedido['id']}` — {pedido['cliente']}")
            st.write(f"**Detalle:** {pedido['detalle_productos']} ({pedido.get('cantidad_total', 1)} cupo/s)")
            st.write(f"**Franja de retiro:** {pedido['franja']} | **Pago:** {pedido['pago']} ({formato_clp(pedido['precio'])})")
            st.progress(progreso_map.get(estado, 0))
            if estado == "Recibido":
                st.info("🕒 Estado: **Recibido** (En cola de preparación)")
            elif estado == "En preparación":
                st.warning("👨‍🍳 Estado: **En preparación** (Tu pedido se está armando)")
            elif estado == "Listo":
                st.success("✅ Estado: **¡LISTO PARA RETIRAR!** Acércate al mesón de entrega.")
            elif estado == "Entregado":
                st.write(f"✔️ Estado: **Entregado** (Retirado a las {pedido['hora_entrega']})")
            elif estado == "Descartado":
                st.error("❌ Estado: **Descartado / Cancelado** (Acércate al mesón de atención para más detalles)")
        with col_qr:
            qr_bytes = generar_qr_image(f"PEDIDO:{pedido['id']}|CLIENTE:{pedido['cliente']}|FRANJA:{pedido['franja']}")
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
    
    if st.sidebar.button("🗑️ Vaciar cupos y reiniciar", type="primary", use_container_width=True):
        db_orders.clear()
        st.session_state.mis_pedidos.clear()
        st.session_state.carrito = {prod: 0 for prod in MENU.keys()}
        st.toast("✅ Todos los pedidos fueron eliminados y los cupos reiniciados.")
        st.rerun()

    if st.sidebar.button("Cerrar sesión", use_container_width=True):
        st.session_state.personal_autenticado = False
        st.rerun()

# ==========================================
# VISTA 1: ESTUDIANTE
# ==========================================
if modo == "📱 Estudiante (Realizar Pedido)":
    # Mostrar pop-up si se acaba de confirmar un pedido
    if st.session_state.pedido_popup is not None:
        pedido_recien_creado = st.session_state.pedido_popup
        st.session_state.pedido_popup = None
        mostrar_popup_confirmacion(pedido_recien_creado)

    if os.path.exists("logo.jpeg"):
        st.image("logo.jpeg", width=360)
    else:
        st.title("🍔 Domeyko GO - Casino ULS")

    st.subheader("Sistema de Pedidos Anticipados por QR")

    # 1) Seguimiento en vivo condicional
    intervalo_seguimiento = REFRESH_SEGUIMIENTO_ESTUDIANTE if st.session_state.mis_pedidos else None

    @st.fragment(run_every=intervalo_seguimiento)
    def seccion_seguimiento_vivo():
        if st.session_state.mis_pedidos:
            col_titulo, col_btn = st.columns([4, 1])
            with col_titulo:
                st.markdown("### 📍 Seguimiento en Vivo de tu Pedido")
            with col_btn:
                if st.button("🔄 Actualizar", key="btn_refresh_est"):
                    st.rerun()

            for pid in reversed(st.session_state.mis_pedidos):
                pedido_actual = next((o for o in db_orders if o["id"] == pid), None)
                if pedido_actual:
                    mostrar_tarjeta_seguimiento(pedido_actual)
            st.markdown("---")

    seccion_seguimiento_vivo()

    # 2) Catálogo con tarjetas visuales estilo menú (2 columnas)
    st.markdown("### 🛍️ Arma tu Pedido")
    total_items_carrito = sum(st.session_state.carrito.values())
    st.caption(f"Selecciona hasta **{MAX_ITEMS_CARRITO} productos** por pedido (1 producto = 1 cupo en la franja horaria).")

    productos_lista = list(MENU.keys())
    for i in range(0, len(productos_lista), 2):
        cols_cards = st.columns(2)
        for j in range(2):
            if i + j < len(productos_lista):
                prod = productos_lista[i + j]
                info = MENU[prod]
                cant_actual = st.session_state.carrito[prod]

                with cols_cards[j]:
                    with st.container(border=True):
                        c_img, c_det = st.columns([1.1, 1.6])
                        with c_img:
                            st.image(obtener_imagen_producto(prod), use_container_width=True)
                        with c_det:
                            st.markdown(f"#### {prod.upper()}")
                            st.caption(info["desc"])
                            st.markdown(f"**{formato_clp(info['precio'])}**")
                            
                            b_menos, b_cant, b_mas = st.columns([1, 1.2, 1])
                            with b_menos:
                                if st.button("➖", key=f"dec_{prod}", disabled=(cant_actual == 0), use_container_width=True):
                                    st.session_state.carrito[prod] -= 1
                                    st.rerun()
                            with b_cant:
                                st.markdown(f"<div style='text-align:center; padding-top:6px; font-weight:bold;'>{cant_actual}</div>", unsafe_allow_html=True)
                            with b_mas:
                                if st.button("➕", key=f"inc_{prod}", disabled=(total_items_carrito >= MAX_ITEMS_CARRITO), use_container_width=True):
                                    st.session_state.carrito[prod] += 1
                                    st.rerun()

    # Resumen rápido del carrito
    st.markdown("---")
    if total_items_carrito == 0:
        st.info("🛒 Tu carrito está vacío. Usa el botón **➕** en los productos de arriba para agregar (máx. 3).")
    else:
        resumen_items = [f"{cant}x {prod}" for prod, cant in st.session_state.carrito.items() if cant > 0]
        total_pagar = sum(MENU[prod]["precio"] * cant for prod, cant in st.session_state.carrito.items())
        with st.container(border=True):
            st.markdown(f"**🛒 Resumen del Carrito ({total_items_carrito}/{MAX_ITEMS_CARRITO} productos = {total_items_carrito} cupo/s):** " + " + ".join(resumen_items))
            st.markdown(f"**Total a Pagar:** {formato_clp(total_pagar)}")

    # 3) Datos del estudiante y franja horaria
    st.markdown("### 📝 Datos de Retiro y Pago")
    nombre_cliente = st.text_input("Tu Nombre y Apellido (para llamarte en el mesón):", placeholder="Ej. Camila Rojas")

    @st.fragment(run_every=REFRESH_CUPOS_ESTUDIANTE)
    def selector_franja_vivo():
        col_f_titulo, col_f_btn = st.columns([4, 1])
        with col_f_titulo:
            st.markdown("**Selecciona la Franja Horaria de Retiro**")
        with col_f_btn:
            if st.button("🔄 Cupos", key="btn_refresh_cupos"):
                st.rerun()
        
        cols = st.columns(len(TIME_SLOTS))
        for idx, slot in enumerate(TIME_SLOTS):
            libres = max(0, LIMIT_PER_SLOT - contar_cupos_ocupados_franja(slot))
            with cols[idx]:
                st.metric(
                    label=slot,
                    value=f"{libres} / {LIMIT_PER_SLOT}",
                    delta="Disponible" if libres > 0 else "Agotado",
                    delta_color="normal" if libres > 0 else "off"
                )

        def formatear_franja(slot):
            libres = max(0, LIMIT_PER_SLOT - contar_cupos_ocupados_franja(slot))
            if libres > 0:
                return f"{slot} ({libres} cupos disponibles)"
            return f"{slot} (AGOTADO)"

        st.selectbox(
            "Franjas de retiro disponibles:",
            options=TIME_SLOTS,
            format_func=formatear_franja,
            key="franja_elegida"
        )

    selector_franja_vivo()

    # Reglas dinámicas de medio de pago según el carrito
    seleccionados = [prod for prod, cant in st.session_state.carrito.items() if cant > 0]
    tiene_no_baes = any(not MENU[p]["baes"] for p in seleccionados)
    tiene_solo_baes = any(MENU[p]["solo_baes"] for p in seleccionados)

    if tiene_solo_baes and tiene_no_baes:
        st.error("⚠️ No puedes mezclar 'Menú BAES' con 'Colación' en el mismo pedido porque tienen medios de pago incompatibles.")
        metodos_pago = []
    elif tiene_solo_baes:
        metodos_pago = ["BAES / JUNAEB"]
        st.info("💳 Tu carrito incluye 'Menú BAES', por lo que el pago es exclusivo con tarjeta BAES / JUNAEB.")
    elif tiene_no_baes:
        metodos_pago = ["Débito / Crédito", "Efectivo en Caja"]
        st.warning("⚠️ Nota: El producto 'Colación' no admite pago con tarjeta BAES / JUNAEB.")
    else:
        metodos_pago = ["Débito / Crédito", "Efectivo en Caja", "BAES / JUNAEB"]

    pago_sel = st.selectbox("Selecciona tu medio de pago:", metodos_pago if metodos_pago else ["Sin medios compatibles"])

    # Verificación de límite de pedidos por minuto (cooldown)
    ahora_ts = time.time()
    segundos_transcurridos = ahora_ts - st.session_state.ultimo_pedido_ts
    en_cooldown = segundos_transcurridos < COOLDOWN_SEGUNDOS
    segundos_restantes = int(COOLDOWN_SEGUNDOS - segundos_transcurridos)

    if en_cooldown:
        st.warning(f"⏳ Control anti-spam: debes esperar **{segundos_restantes} segundos** antes de enviar otro pedido desde este dispositivo.")

    if st.button("Confirmar y Pagar Pedido", type="primary", disabled=(total_items_carrito == 0 or not metodos_pago or en_cooldown)):
        franja_sel = st.session_state.get("franja_elegida", TIME_SLOTS[0])
        cupos_libres_reales = LIMIT_PER_SLOT - contar_cupos_ocupados_franja(franja_sel)

        if not nombre_cliente.strip():
            st.error("⚠️ Por favor ingresa tu nombre y apellido para identificar tu pedido al retirar.")
        elif total_items_carrito > cupos_libres_reales:
            st.error(f"⚠️ La franja **{franja_sel}** solo tiene **{cupos_libres_reales} cupo(s)** disponibles y tu carrito requiere **{total_items_carrito} cupos**. Reduce la cantidad o elige otro horario.")
        else:
            total_pagar = sum(MENU[prod]["precio"] * cant for prod, cant in st.session_state.carrito.items())
            exito, tx_id = procesar_pago(pago_sel, total_pagar)
            if exito:
                order_id = generar_id_pedido()
                hora_actual = datetime.now().strftime("%H:%M:%S")
                detalle_str = " + ".join([f"{cant}x {prod}" for prod, cant in st.session_state.carrito.items() if cant > 0])
                primer_prod = seleccionados[0] if len(seleccionados) == 1 else "Pedido Múltiple"

                nuevo_pedido = {
                    "id": order_id,
                    "cliente": nombre_cliente.strip(),
                    "producto": primer_prod,
                    "detalle_productos": detalle_str,
                    "cantidad_total": total_items_carrito,
                    "precio": total_pagar,
                    "franja": franja_sel,
                    "pago": pago_sel,
                    "tx_id": tx_id,
                    "estado": "Recibido",
                    "hora_registro": hora_actual,
                    "hora_entrega": "-"
                }
                db_orders.append(nuevo_pedido)
                st.session_state.mis_pedidos.append(order_id)
                st.session_state.ultimo_pedido_ts = time.time()
                st.session_state.carrito = {prod: 0 for prod in MENU.keys()}
                st.session_state.pedido_popup = nuevo_pedido
                st.rerun()

    # Buscador secundario por si se consulta desde otro navegador o dispositivo
    with st.expander("🔍 Consultar otro pedido por código"):
        busqueda_id = st.text_input("Ingresa el código de pedido (ej. ORD-1234):").strip().upper()
        if busqueda_id:
            pedido_encontrado = next((o for o in db_orders if o["id"] == busqueda_id), None)
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

    def renderizar_tarjeta_kds(order: dict, prefix_key: str):
        with st.container(border=True):
            c_head, c_disc = st.columns([4, 1])
            with c_head:
                st.markdown(f"#### 📦 `{order['id']}` — 👤 **{order.get('cliente', 'Sin nombre')}**")
                st.write(f"**Detalle:** {order.get('detalle_productos', order['producto'])} ({order.get('cantidad_total', 1)} cupo/s)")
                st.caption(f"🕒 Pedido: {order['hora_registro']} | 💳 {order['pago']} ({formato_clp(order['precio'])}) | TX: `{order['tx_id']}`")
            with c_disc:
                if order["estado"] != "Descartado":
                    if st.button(
                        "❌ Descartar",
                        key=f"{prefix_key}_disc_{order['id']}",
                        help="Cancela el pedido y libera sus cupos en esta franja",
                        use_container_width=True
                    ):
                        order["estado"] = "Descartado"
                        order["hora_entrega"] = "Descartado"
                        st.rerun()

            b1, b2, b3, b4 = st.columns(4)
            botones_config = [
                (b1, "Recibido", "📥 Recibido", "secondary"),
                (b2, "En preparación", "👨‍🍳 Preparando", "secondary"),
                (b3, "Listo", "🔔 Listo", "secondary"),
                (b4, "Entregado", "✅ Entregado", "primary"),
            ]

            for col_btn, estado_obj, etiqueta, tipo_btn in botones_config:
                with col_btn:
                    es_actual = (order["estado"] == estado_obj)
                    texto_btn = f"• {etiqueta} •" if es_actual else etiqueta
                    if st.button(
                        texto_btn,
                        key=f"{prefix_key}_btn_{order['id']}_{estado_obj}",
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

    @st.fragment(run_every=REFRESH_KDS_OPERADOR)
    def panel_pedidos_kds():
        pedidos_activos = [o for o in db_orders if o["estado"] not in ["Entregado", "Descartado"]]
        pedidos_terminados = [o for o in db_orders if o["estado"] in ["Entregado", "Descartado"]]

        col_m1, col_m2, col_r = st.columns([2, 2, 1])
        with col_m1:
            st.metric("Pedidos Activos en Cocina", len(pedidos_activos))
        with col_m2:
            st.metric("Pedidos Terminados / Descartados", len(pedidos_terminados))
        with col_r:
            if st.button("🔄 Refrescar", key="btn_refresh_kds"):
                st.rerun()

        tab_activos, tab_historial = st.tabs([
            f"🔥 Pedidos Activos por Franja ({len(pedidos_activos)})",
            f"📁 Terminados y Descartados ({len(pedidos_terminados)})"
        ])

        with tab_activos:
            if not pedidos_activos:
                st.info("No hay pedidos pendientes en este momento. Esperando órdenes...")
            else:
                for slot in TIME_SLOTS:
                    ordenes_franja = [o for o in pedidos_activos if o["franja"] == slot]
                    cupos_usados = contar_cupos_ocupados_franja(slot)
                    st.markdown(f"### ⏰ Franja {slot} — Cupos ocupados: {cupos_usados}/{LIMIT_PER_SLOT}")
                    if not ordenes_franja:
                        st.caption("Sin pedidos activos en esta franja.")
                    else:
                        for order in ordenes_franja:
                            renderizar_tarjeta_kds(order, "act")
                    st.markdown("---")

        with tab_historial:
            if not pedidos_terminados:
                st.info("Aún no hay pedidos entregados o descartados.")
            else:
                for order in reversed(pedidos_terminados):
                    st.caption(f"Franja: **{order['franja']}** | Estado final: **{order['estado'].upper()}** | Cierre: {order['hora_entrega']}")
                    renderizar_tarjeta_kds(order, "hist")

    panel_pedidos_kds()

# ==========================================
# VISTA 3: MÉTRICAS Y EXPORTACIÓN
# ==========================================
else:
    if not verificar_login_personal():
        st.stop()

    st.title("📊 Análisis de Datos y Trazabilidad del Prototipo")
    st.markdown("Registro cuantitativo de órdenes para validación de tiempos de atención.")

    if not db_orders:
        st.info("Aún no hay datos recolectados. Registra algunos pedidos desde la vista de estudiante.")
    else:
        df = pd.DataFrame(db_orders)
        st.dataframe(df, use_container_width=True)

        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar Reporte de Tiempos (CSV)",
            data=csv_data,
            file_name=f"reporte_cafeteria_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            type="primary"
        )