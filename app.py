import streamlit as st
import streamlit.components.v1 as components
import random
import string
import pandas as pd
import io
import os
import time
import tempfile
import qrcode
from datetime import datetime
from zoneinfo import ZoneInfo

# Configuración de página
st.set_page_config(page_title="Domeyko GO - Casino ULS", page_icon="🍔", layout="wide")

# ==========================================
# PARÁMETROS DEL SISTEMA Y VERSIÓN
# ==========================================
# True  -> Versión de Pruebas: muestra interruptor para activar/desactivar validación horaria.
# False -> Versión Oficial: oculta el interruptor y exige siempre pedir antes del inicio de la franja.
MODO_PRUEBAS = True

# Color de fondo opcional (deja None para usar el tema por defecto de Streamlit)
COLOR_FONDO_APP = None

CLAVE_PERSONAL = "domeyko2026"  # Contraseña para Caja, Cocina y Métricas
LIMIT_PER_SLOT = 10             # Máximo 10 unidades/cupos por franja de 15 min
MAX_ITEMS_CARRITO = 3           # Máximo 3 productos por pedido
COOLDOWN_SEGUNDOS = 60          # Límite de 1 pedido por minuto por dispositivo
ZONA_HORARIA_CL = ZoneInfo("America/Santiago")

TIME_SLOTS = [
    "13:00 - 13:15",
    "13:15 - 13:30",
    "13:30 - 13:45",
    "13:45 - 14:00"
]

# Tasas de refresco optimizadas para conectividad universitaria (en segundos)
REFRESH_SEGUIMIENTO_ESTUDIANTE = 8
REFRESH_CUPOS_ESTUDIANTE = 15
REFRESH_OPERACION = 5

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

# ==========================================
# COMPONENTE BIDIRECCIONAL NATIVO DE ESCÁNER QR
# ==========================================
@st.cache_resource
def inicializar_componente_qr():
    comp_dir = os.path.join(tempfile.gettempdir(), "domeyko_qr_reader_v2")
    os.makedirs(comp_dir, exist_ok=True)
    index_path = os.path.join(comp_dir, "index.html")

    html_code = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"></script>
  <style>
    body {
      margin: 0;
      padding: 8px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      text-align: center;
      background: transparent;
    }
    #reader {
      width: 100%;
      max-width: 440px;
      margin: 0 auto;
      border-radius: 12px;
      overflow: hidden;
      border: 3px solid #0d6efd;
    }
    #qr-status {
      margin-top: 10px;
      font-size: 16px;
      font-weight: 700;
      color: #0d6efd;
    }
  </style>
</head>
<body>
  <div id="reader"></div>
  <div id="qr-status">📷 Iniciando cámara... Apunta el código QR frente al lente</div>

  <script>
    let streamlitListo = false;

    function sendMessageToStreamlitClient(type, data) {
      const outData = Object.assign({
        isStreamlitMessage: true,
        type: type,
      }, data);
      window.parent.postMessage(outData, "*");
    }

    function setComponentValue(value) {
      sendMessageToStreamlitClient("streamlit:setComponentValue", {
        value: value,
        dataType: "json"
      });
    }

    function setFrameHeight(height) {
      sendMessageToStreamlitClient("streamlit:setFrameHeight", { height: height });
    }

    window.addEventListener("message", function(event) {
      if (event.data && event.data.type === "streamlit:render") {
        streamlitListo = true;
        setFrameHeight(390);
      }
    });

    // Asegurar handshake con Streamlit antes de permitir lectura
    const readyInterval = setInterval(() => {
      if (streamlitListo) {
        clearInterval(readyInterval);
      } else {
        sendMessageToStreamlitClient("streamlit:componentReady", { apiVersion: 1 });
        setFrameHeight(390);
      }
    }, 200);

    sendMessageToStreamlitClient("streamlit:componentReady", { apiVersion: 1 });
    setFrameHeight(390);

    const html5QrCode = new Html5Qrcode("reader");
    let yaDetectado = false;

    function onScanSuccess(decodedText) {
      if (yaDetectado) return;
      yaDetectado = true;
      const statusEl = document.getElementById("qr-status");
      statusEl.innerText = "✅ ¡QR leído! Actualizando pantalla...";
      statusEl.style.color = "#198754";

      // Enviar valor inmediatamente a Python
      setComponentValue(decodedText);

      // Detener cámara en segundo plano sin bloquear el envío
      html5QrCode.stop().catch(() => {});
    }

    html5QrCode.start(
      { facingMode: "environment" },
      { fps: 12, qrbox: { width: 240, height: 240 } },
      onScanSuccess,
      () => {}
    ).catch(() => {
      const statusEl = document.getElementById("qr-status");
      statusEl.innerText = "⚠️ No se pudo acceder a la cámara. Revisa los permisos del navegador.";
      statusEl.style.color = "#dc3545";
    });

    window.addEventListener("beforeunload", () => {
      if (html5QrCode.isScanning) {
        html5QrCode.stop().catch(() => {});
      }
    });
  </script>
</body>
</html>
"""
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html_code)

    return components.declare_component("domeyko_qr_scanner_v2", path=comp_dir)

escaner_qr_nativo = inicializar_componente_qr()

if COLOR_FONDO_APP:
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-color: {COLOR_FONDO_APP};
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

# ==========================================
# ESTADO COMPARTIDO EN SERVIDOR
# ==========================================
@st.cache_resource
def obtener_base_datos():
    return []

@st.cache_resource
def obtener_base_encuestas():
    return []

@st.cache_resource
def obtener_config_operativa():
    return {
        "validar_horario": True,
        "productos_agotados": {prod: False for prod in MENU.keys()}
    }

db_orders = obtener_base_datos()
db_surveys = obtener_base_encuestas()
config_op = obtener_config_operativa()

if not MODO_PRUEBAS:
    config_op["validar_horario"] = True

# Estado local individual de cada celular/navegador
if "mis_pedidos" not in st.session_state:
    st.session_state.mis_pedidos = []

if "pedidos_notificados_aprobados" not in st.session_state:
    st.session_state.pedidos_notificados_aprobados = set()

if "pedidos_notificados_listos" not in st.session_state:
    st.session_state.pedidos_notificados_listos = set()

if "personal_autenticado" not in st.session_state:
    st.session_state.personal_autenticado = False

if "ultimo_pedido_ts" not in st.session_state:
    st.session_state.ultimo_pedido_ts = 0.0

if "pedido_popup" not in st.session_state:
    st.session_state.pedido_popup = None

if "carrito" not in st.session_state:
    st.session_state.carrito = {prod: 0 for prod in MENU.keys()}

if "franja_elegida" not in st.session_state:
    st.session_state.franja_elegida = None

if "pago_elegido" not in st.session_state:
    st.session_state.pago_elegido = None

if "escaner_abierto" not in st.session_state:
    st.session_state.escaner_abierto = False

if "scanner_session_id" not in st.session_state:
    st.session_state.scanner_session_id = 0

if "ultimo_resultado_qr" not in st.session_state:
    st.session_state.ultimo_resultado_qr = None

# ==========================================
# FUNCIONES AUXILIARES
# ==========================================
def ahora_chile() -> datetime:
    return datetime.now(ZONA_HORARIA_CL)

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
    return sum(
        o.get("cantidad_total", 1)
        for o in db_orders
        if o["franja"] == franja and o["estado"] != "Descartado"
    )

def franja_esta_cerrada_por_hora(franja: str) -> bool:
    if not config_op.get("validar_horario", True):
        return False
    hora_inicio_str = franja.split("-")[0].strip()
    h_ini, m_ini = map(int, hora_inicio_str.split(":"))
    ahora = ahora_chile()
    inicio_franja = ahora.replace(hour=h_ini, minute=m_ini, second=0, microsecond=0)
    return ahora >= inicio_franja

def actualizar_estado_pedido(order: dict, nuevo_estado: str, motivo_descarte: str = "Descartado"):
    """Registra la transición de estado y su marca de tiempo exacta."""
    ahora_str = ahora_chile().strftime("%H:%M:%S")
    order["estado"] = nuevo_estado

    if nuevo_estado == "Aprobado - Pendiente de Pago":
        if order.get("hora_aprobacion", "-") == "-":
            order["hora_aprobacion"] = ahora_str
    elif nuevo_estado == "En preparación":
        if order.get("hora_aprobacion", "-") == "-":
            order["hora_aprobacion"] = ahora_str
        if order.get("hora_pago", "-") == "-":
            order["hora_pago"] = ahora_str
    elif nuevo_estado == "Listo":
        if order.get("hora_listo", "-") == "-":
            order["hora_listo"] = ahora_str
    elif nuevo_estado == "Cliente en mesón":
        if order.get("hora_listo", "-") == "-":
            order["hora_listo"] = ahora_str
        if order.get("hora_llegada_cliente", "-") == "-":
            order["hora_llegada_cliente"] = ahora_str
    elif nuevo_estado == "Entregado":
        if order.get("hora_listo", "-") == "-":
            order["hora_listo"] = ahora_str
        if order.get("hora_llegada_cliente", "-") == "-":
            order["hora_llegada_cliente"] = ahora_str
        order["hora_entrega"] = ahora_str
    elif nuevo_estado == "Descartado":
        order["hora_entrega"] = motivo_descarte

def calcular_minutos_diferencia(h_inicio: str, h_fin: str):
    invalidos = {"-", "Descartado", "Rechazado en caja", "Cancelado por usuario", None, ""}
    if h_inicio in invalidos or h_fin in invalidos:
        return None
    try:
        t1 = datetime.strptime(h_inicio, "%H:%M:%S")
        t2 = datetime.strptime(h_fin, "%H:%M:%S")
        diff = (t2 - t1).total_seconds() / 60.0
        return round(max(0.0, diff), 2)
    except ValueError:
        return None

def obtener_imagen_producto(prod: str) -> str:
    ruta_local = MENU[prod]["img_local"]
    if os.path.exists(ruta_local):
        return ruta_local
    return MENU[prod]["img_fallback"]

@st.cache_data
def generar_qr_image(data_text: str):
    qr = qrcode.QRCode(version=1, box_size=12, border=3)
    qr.add_data(data_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def procesar_escaneo_qr_totem(token: str):
    """Notifica a cocina que el cliente llegó al punto de escaneo con su QR."""
    if not token.startswith("DOMEYKO-QR|"):
        return "error", "❌ Formato de QR no reconocido por Domeyko GO."
    
    partes = token.split("|")
    oid_esc = partes[1] if len(partes) > 1 else ""
    tx_esc = partes[2] if len(partes) > 2 else ""
    pedido_obj = next(
        (o for o in db_orders if o["id"] == oid_esc and o["tx_id"] == tx_esc),
        None
    )

    if not pedido_obj:
        return "error", "❌ Código QR no corresponde a una orden pagada y válida."
    if pedido_obj["estado"] in ["Pendiente aprobación", "Aprobado - Pendiente de Pago"]:
        return "warning", f"💳 El pedido **{oid_esc}** ({pedido_obj['cliente']}) aún no ha completado su aprobación/pago en Caja."
    if pedido_obj["estado"] == "En preparación":
        return "warning", f"👨‍🍳 El pedido **{oid_esc}** ({pedido_obj['cliente']}) todavía se está preparando en cocina."
    if pedido_obj["estado"] == "Cliente en mesón":
        return "info", f"📣 Cocina ya fue notificada para el pedido **{oid_esc}** de **{pedido_obj['cliente']}**."
    if pedido_obj["estado"] == "Entregado":
        return "warning", f"⚠️ El pedido **{oid_esc}** ya fue entregado a las {pedido_obj['hora_entrega']}."
    if pedido_obj["estado"] == "Descartado":
        return "error", f"❌ El pedido **{oid_esc}** fue cancelado/rechazado."

    actualizar_estado_pedido(pedido_obj, "Cliente en mesón")
    return "success", f"📣 ¡Notificación enviada a cocina! **{pedido_obj['cliente']}** (Pedido **{oid_esc}**) está esperando retiro en mesón."

@st.dialog("📩 ¡Solicitud Enviada a Caja!")
def mostrar_popup_confirmacion(pedido: dict):
    st.info(f"Hola **{pedido['cliente']}**, tu reserva de cupos ingresó a **Caja** para verificar stock.")
    st.markdown(f"### Código de Solicitud: `{pedido['id']}`")
    st.write(f"**Franja reservada:** {pedido['franja']}")
    st.write(f"**Detalle:** {pedido['detalle_productos']}")
    st.write(f"**Monto a pagar tras aprobación:** {formato_clp(pedido['precio'])} ({pedido['pago']})")
    st.warning("⚠️ **Importante:** No se te cobrará nada hasta que Caja apruebe tu pedido. Revisa el seguimiento aquí abajo para completar el pago cuando sea aprobado.")

    if st.button("Entendido, ir al seguimiento", type="primary", use_container_width=True):
        st.rerun()

def mostrar_tarjeta_seguimiento(pedido: dict, permitir_acciones: bool = False):
    progreso_map = {
        "Pendiente aprobación": 15,
        "Aprobado - Pendiente de Pago": 35,
        "En preparación": 60,
        "Listo": 85,
        "Cliente en mesón": 92,
        "Entregado": 100,
        "Descartado": 0
    }
    estado = pedido["estado"]

    if estado == "Aprobado - Pendiente de Pago" and pedido["id"] not in st.session_state.pedidos_notificados_aprobados:
        st.session_state.pedidos_notificados_aprobados.add(pedido["id"])
        st.toast(f"✅ ¡Stock confirmado! Paga tu pedido {pedido['id']} para enviarlo a cocina.", icon="💳")

    if estado == "Listo" and pedido["id"] not in st.session_state.pedidos_notificados_listos:
        st.session_state.pedidos_notificados_listos.add(pedido["id"])
        st.toast(f"🔔 ¡{pedido['cliente']}, tu pedido {pedido['id']} está LISTO! Escanea tu QR al llegar.", icon="✅")

    with st.container(border=True):
        col_info, col_qr = st.columns([2, 1.3])
        with col_info:
            st.markdown(f"#### 🧾 Pedido `{pedido['id']}` — {pedido['cliente']}")
            st.write(f"**Detalle:** {pedido['detalle_productos']} ({pedido.get('cantidad_total', 1)} cupo/s)")
            st.write(f"**Franja de retiro:** {pedido['franja']} | **Pago:** {pedido['pago']} ({formato_clp(pedido['precio'])})")
            st.progress(progreso_map.get(estado, 0))

            if estado == "Pendiente aprobación":
                st.info("🕒 Paso 1: **Esperando aprobación en Caja** (Sin cobro aún mientras se verifica stock)")
                if permitir_acciones:
                    if st.button(
                        "🗑️ Cancelar Solicitud (libera cupos)",
                        key=f"cancel_user_{pedido['id']}",
                        help="Puedes anular tu solicitud antes de pagar."
                    ):
                        actualizar_estado_pedido(pedido, "Descartado", motivo_descarte="Cancelado por usuario")
                        st.toast(f"Solicitud {pedido['id']} cancelada. Cupos liberados.")
                        st.rerun()

            elif estado == "Aprobado - Pendiente de Pago":
                if pedido["pago"] == "Efectivo en Caja":
                    st.warning("💵 **¡Stock aprobado!** Acércate a Caja a pagar en efectivo para que tu pedido pase a Cocina.")
                else:
                    st.warning(f"💳 **¡Stock aprobado por Caja!** Completa tu pago con **{pedido['pago']}** para enviar el pedido a Cocina.")
                    if permitir_acciones:
                        c_pay, c_can = st.columns([2, 1])
                        with c_pay:
                            if st.button(
                                f"💳 Pagar {formato_clp(pedido['precio'])} Ahora ({pedido['pago']})",
                                key=f"pagar_user_{pedido['id']}",
                                type="primary",
                                use_container_width=True
                            ):
                                exito, tx_id = procesar_pago(pedido["pago"], pedido["precio"])
                                if exito:
                                    pedido["tx_id"] = tx_id
                                    actualizar_estado_pedido(pedido, "En preparación")
                                    st.toast(f"✅ Pago confirmado ({tx_id}). Pedido enviado a Cocina.")
                                    st.rerun()
                        with c_can:
                            if st.button(
                                "🗑️ Cancelar",
                                key=f"cancel_unpaid_{pedido['id']}",
                                use_container_width=True
                            ):
                                actualizar_estado_pedido(pedido, "Descartado", motivo_descarte="Cancelado por usuario")
                                st.rerun()

            elif estado == "En preparación":
                st.info(f"👨‍🍳 **Pagado (`{pedido['tx_id']}`) y En Preparación** — Cocina ya está armando tu pedido.")

            elif estado == "Listo":
                st.success("🔔 **¡TU PEDIDO ESTÁ LISTO!** Acércate al punto de retiro y escanea tu QR para avisar a cocina.")
                if permitir_acciones:
                    if st.button(
                        "📲 Escanear QR en Punto de Retiro (Avisar a Cocina)",
                        key=f"checkin_user_{pedido['id']}",
                        type="primary"
                    ):
                        actualizar_estado_pedido(pedido, "Cliente en mesón")
                        st.toast("📣 Cocina notificada. Ya van a entregarte tu pedido.")
                        st.rerun()

            elif estado == "Cliente en mesón":
                st.success("📣 **¡Cocina notificada!** Espera en el mesón, el personal ya va a entregarte tu pedido.")

            elif estado == "Entregado":
                st.write(f"✔️ Estado: **Entregado** (Retirado a las {pedido['hora_entrega']} | TX: `{pedido['tx_id']}`)")

            elif estado == "Descartado":
                st.error(f"❌ Estado: **Cancelado / Sin Stock** ({pedido.get('hora_entrega', 'Descartado')})")

        with col_qr:
            if pedido["tx_id"] != "PENDIENTE" and estado != "Descartado":
                qr_bytes = generar_qr_image(f"DOMEYKO-QR|{pedido['id']}|{pedido['tx_id']}")
                st.image(qr_bytes, caption=f"QR Retiro {pedido['id']}", width=230)
            else:
                st.caption("🔒 El QR de retiro se activará una vez aprobado y pagado el pedido.")

def verificar_login_personal() -> bool:
    if st.session_state.personal_autenticado:
        return True

    st.title("🔒 Acceso Restringido - Personal Cafetería")
    st.markdown("Ingresa la clave operativa para acceder a Caja, Cocina y Métricas.")
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

if MODO_PRUEBAS:
    st.sidebar.warning("🧪 ENTORNO DE PRUEBAS")

st.sidebar.title("📌 Menú de Navegación")
modo = st.sidebar.radio("Selecciona la vista:", [
    "📱 Estudiante (Realizar Pedido)",
    "💵 Caja (Aprobación y Stock)",
    "🍳 Cocina (Preparación y Entrega)",
    "📊 Panel de Métricas / Exportación"
])

if st.session_state.personal_autenticado:
    st.sidebar.markdown("---")
    st.sidebar.success("🔓 Sesión de personal activa")

    if MODO_PRUEBAS:
        val_horaria = st.sidebar.toggle(
            "⏰ Bloquear franjas ya iniciadas",
            value=config_op["validar_horario"],
            help="Si está activo, impide pedir en franjas cuya hora de inicio ya pasó."
        )
        if val_horaria != config_op["validar_horario"]:
            config_op["validar_horario"] = val_horaria
            st.rerun()
    
    if st.sidebar.button("🗑️ Vaciar cupos y reiniciar", type="primary", use_container_width=True):
        db_orders.clear()
        db_surveys.clear()
        st.session_state.mis_pedidos.clear()
        st.session_state.pedidos_notificados_aprobados.clear()
        st.session_state.pedidos_notificados_listos.clear()
        st.session_state.carrito = {prod: 0 for prod in MENU.keys()}
        st.session_state.franja_elegida = None
        st.session_state.pago_elegido = None
        st.session_state.escaner_abierto = False
        st.session_state.ultimo_resultado_qr = None
        config_op["productos_agotados"] = {prod: False for prod in MENU.keys()}
        st.toast("✅ Pedidos y encuestas eliminados, stock restaurado y cupos reiniciados.")
        st.rerun()

    if st.sidebar.button("Cerrar sesión", use_container_width=True):
        st.session_state.personal_autenticado = False
        st.session_state.escaner_abierto = False
        st.rerun()

# ==========================================
# VISTA 1: ESTUDIANTE
# ==========================================
if modo == "📱 Estudiante (Realizar Pedido)":
    st.markdown("""
        <style>
        div[data-testid="stTextInput"] input {
            font-size: 19px !important;
            min-height: 54px !important;
            padding: 12px 16px !important;
            border-radius: 10px !important;
            border: 2px solid #4a5568 !important;
        }
        div[data-testid="stTextInput"] input:focus {
            border-color: #28a745 !important;
            box-shadow: 0 0 0 2px rgba(40, 167, 69, 0.25) !important;
        }
        div[data-testid="stTextInput"] label p {
            font-size: 17px !important;
            font-weight: 700 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    if st.session_state.pedido_popup is not None:
        pedido_recien_creado = st.session_state.pedido_popup
        st.session_state.pedido_popup = None
        mostrar_popup_confirmacion(pedido_recien_creado)

    if os.path.exists("logo.jpeg"):
        st.image("logo.jpeg", width=360)
    else:
        st.title("🍔 Domeyko GO - Casino ULS")

    st.subheader("Sistema de Pedidos Anticipados por QR")

    # 1) Catálogo con tarjetas visuales estilo menú (2 columnas)
    st.markdown("### 🛍️ 1. Arma tu Pedido")
    
    for prod, esta_agotado in config_op["productos_agotados"].items():
        if esta_agotado and st.session_state.carrito[prod] > 0:
            st.session_state.carrito[prod] = 0

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
                agotado = config_op["productos_agotados"].get(prod, False)

                with cols_cards[j]:
                    with st.container(border=True):
                        c_img, c_det = st.columns([1.1, 1.6])
                        with c_img:
                            st.image(obtener_imagen_producto(prod), use_container_width=True)
                        with c_det:
                            st.markdown(f"#### {prod.upper()}")
                            st.caption(info["desc"])
                            if agotado:
                                st.markdown(f"~~{formato_clp(info['precio'])}~~ — :red[**🚫 STOCK AGOTADO**]")
                            else:
                                st.markdown(f"**{formato_clp(info['precio'])}**")
                            
                            b_menos, b_cant, b_mas = st.columns([1, 1.2, 1])
                            with b_menos:
                                if st.button("➖", key=f"dec_{prod}", disabled=(cant_actual == 0 or agotado), use_container_width=True):
                                    st.session_state.carrito[prod] -= 1
                                    st.rerun()
                            with b_cant:
                                st.markdown(f"<div style='text-align:center; padding-top:6px; font-weight:bold;'>{cant_actual}</div>", unsafe_allow_html=True)
                            with b_mas:
                                if st.button("➕", key=f"inc_{prod}", disabled=(total_items_carrito >= MAX_ITEMS_CARRITO or agotado), use_container_width=True):
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
            st.markdown(f"**Total Estimado:** {formato_clp(total_pagar)} *(se paga una vez que Caja confirme stock)*")

    # 2) Datos del estudiante (Campo grande)
    st.markdown("### 📝 2. Identificación para Retiro")
    nombre_cliente = st.text_input(
        "👤 Tu Nombre y Apellido (para llamarte en el mesón):",
        placeholder="Escribe aquí tu nombre y apellido (Ej. Camila Rojas)..."
    )

    # 3) Selector de Franja Horaria mediante TARJETAS INTERACTIVAS
    st.markdown("### ⏰ 3. Toca la Franja Horaria de Retiro")

    @st.fragment(run_every=REFRESH_CUPOS_ESTUDIANTE)
    def selector_franja_botones():
        col_f_titulo, col_f_btn = st.columns([4, 1])
        with col_f_titulo:
            if config_op.get("validar_horario", True):
                st.caption(f"Hora actual: **{ahora_chile().strftime('%H:%M')}** — Toca una tarjeta disponible para seleccionarla.")
            else:
                st.caption("Toca una tarjeta de horario para seleccionarla.")
        with col_f_btn:
            if st.button("🔄 Cupos", key="btn_refresh_cupos", use_container_width=True):
                st.rerun()

        franja_actual = st.session_state.franja_elegida
        if franja_actual:
            libres_actual = max(0, LIMIT_PER_SLOT - contar_cupos_ocupados_franja(franja_actual))
            if franja_esta_cerrada_por_hora(franja_actual) or libres_actual == 0:
                st.session_state.franja_elegida = None
                franja_actual = None

        if franja_actual is None:
            for s in TIME_SLOTS:
                if not franja_esta_cerrada_por_hora(s) and (LIMIT_PER_SLOT - contar_cupos_ocupados_franja(s)) > 0:
                    st.session_state.franja_elegida = s
                    franja_actual = s
                    break

        cols = st.columns(len(TIME_SLOTS))
        for idx, slot in enumerate(TIME_SLOTS):
            libres = max(0, LIMIT_PER_SLOT - contar_cupos_ocupados_franja(slot))
            cerrada_hora = franja_esta_cerrada_por_hora(slot)
            sin_cupos = (libres == 0)
            deshabilitada = cerrada_hora or sin_cupos
            es_seleccionada = (st.session_state.franja_elegida == slot) and not deshabilitada

            with cols[idx]:
                with st.container(border=True):
                    if es_seleccionada:
                        st.markdown(f":green[**✅ {slot}**]")
                    else:
                        st.markdown(f"**{slot}**")

                    if cerrada_hora:
                        st.markdown("### CERRADA")
                        st.caption("🔴 Fuera de hora")
                        texto_boton = "Cerrada"
                    elif sin_cupos:
                        st.markdown("### 0 / 10")
                        st.caption("🔴 Sin cupos")
                        texto_boton = "Agotado"
                    else:
                        st.markdown(f"### {libres} / {LIMIT_PER_SLOT}")
                        st.caption("🟢 Disponible")
                        texto_boton = "Seleccionado" if es_seleccionada else "Elegir horario"

                    if st.button(
                        texto_boton,
                        key=f"btn_slot_{idx}",
                        type="primary" if es_seleccionada else "secondary",
                        disabled=deshabilitada,
                        use_container_width=True
                    ):
                        st.session_state.franja_elegida = slot
                        st.rerun()

    selector_franja_botones()

    # 4) Selector de Medio de Pago mediante BOTONES INTERACTIVOS
    st.markdown("### 💳 4. Toca tu Medio de Pago")
    seleccionados = [prod for prod, cant in st.session_state.carrito.items() if cant > 0]
    tiene_no_baes = any(not MENU[p]["baes"] for p in seleccionados)
    tiene_solo_baes = any(MENU[p]["solo_baes"] for p in seleccionados)

    iconos_pago = {
        "Débito / Crédito": "💳",
        "Efectivo en Caja": "💵",
        "BAES / JUNAEB": "🎓"
    }
    desc_pago = {
        "Débito / Crédito": "Tarjeta bancaria",
        "Efectivo en Caja": "Pagar en mesón",
        "BAES / JUNAEB": "Tarjeta Junaeb"
    }

    if tiene_solo_baes and tiene_no_baes:
        st.error("⚠️ No puedes mezclar 'Menú BAES' con 'Colación' en el mismo pedido porque tienen medios de pago incompatibles.")
        metodos_pago = []
    elif tiene_solo_baes:
        metodos_pago = ["BAES / JUNAEB"]
        st.info("🎓 Tu carrito incluye 'Menú BAES', por lo que el pago es exclusivo con tarjeta BAES / JUNAEB.")
    elif tiene_no_baes:
        metodos_pago = ["Débito / Crédito", "Efectivo en Caja"]
        st.warning("⚠️ Nota: El producto 'Colación' no admite pago con tarjeta BAES / JUNAEB.")
    else:
        metodos_pago = ["Débito / Crédito", "Efectivo en Caja", "BAES / JUNAEB"]

    if not metodos_pago:
        st.session_state.pago_elegido = None
    elif st.session_state.pago_elegido not in metodos_pago:
        st.session_state.pago_elegido = metodos_pago[0]

    if metodos_pago:
        cols_pago = st.columns(len(metodos_pago))
        for idx_p, metodo in enumerate(metodos_pago):
            es_pago_sel = (st.session_state.pago_elegido == metodo)
            with cols_pago[idx_p]:
                with st.container(border=True):
                    icono = iconos_pago.get(metodo, "💳")
                    if es_pago_sel:
                        st.markdown(f":green[**✅ {icono} {metodo}**]")
                    else:
                        st.markdown(f"**{icono} {metodo}**")
                    st.caption(desc_pago.get(metodo, ""))
                    if st.button(
                        "Seleccionado" if es_pago_sel else "Elegir medio",
                        key=f"btn_pago_{metodo}",
                        type="primary" if es_pago_sel else "secondary",
                        use_container_width=True
                    ):
                        st.session_state.pago_elegido = metodo
                        st.rerun()

    st.markdown("---")
    ahora_ts = time.time()
    segundos_transcurridos = ahora_ts - st.session_state.ultimo_pedido_ts
    en_cooldown = segundos_transcurridos < COOLDOWN_SEGUNDOS
    segundos_restantes = int(COOLDOWN_SEGUNDOS - segundos_transcurridos)

    if en_cooldown:
        st.warning(f"⏳ Control anti-spam: debes esperar **{segundos_restantes} segundos** antes de enviar otra solicitud desde este dispositivo.")

    franja_sel = st.session_state.franja_elegida
    pago_sel = st.session_state.pago_elegido

    if franja_sel and pago_sel and total_items_carrito > 0:
        st.caption(f"Resumen listo: Franja **{franja_sel}** | Medio de pago **{pago_sel}**")

    if st.button(
        "📩 Enviar Solicitud a Caja (Sin cobro aún)",
        type="primary",
        disabled=(total_items_carrito == 0 or not metodos_pago or not franja_sel or en_cooldown),
        use_container_width=True
    ):
        cupos_libres_reales = LIMIT_PER_SLOT - contar_cupos_ocupados_franja(franja_sel)
        productos_sin_stock = [p for p in seleccionados if config_op["productos_agotados"].get(p, False)]

        if not nombre_cliente.strip():
            st.error("⚠️ Por favor ingresa tu nombre y apellido para identificar tu pedido al retirar.")
        elif productos_sin_stock:
            st.error(f"⚠️ Lo sentimos, el stock de **{', '.join(productos_sin_stock)}** acaba de agotarse.")
        elif franja_esta_cerrada_por_hora(franja_sel):
            st.error(f"⏰ La franja **{franja_sel}** ya comenzó (hora actual {ahora_chile().strftime('%H:%M')}) y no acepta nuevos pedidos.")
        elif total_items_carrito > cupos_libres_reales:
            st.error(f"⚠️ La franja **{franja_sel}** solo tiene **{cupos_libres_reales} cupo(s)** disponibles y tu carrito requiere **{total_items_carrito} cupos**.")
        else:
            total_pagar = sum(MENU[prod]["precio"] * cant for prod, cant in st.session_state.carrito.items())
            order_id = generar_id_pedido()
            hora_actual = ahora_chile().strftime("%H:%M:%S")
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
                "tx_id": "PENDIENTE",
                "estado": "Pendiente aprobación",
                "hora_registro": hora_actual,
                "hora_aprobacion": "-",
                "hora_pago": "-",
                "hora_listo": "-",
                "hora_llegada_cliente": "-",
                "hora_entrega": "-"
            }
            db_orders.append(nuevo_pedido)
            st.session_state.mis_pedidos.append(order_id)
            st.session_state.ultimo_pedido_ts = time.time()
            st.session_state.carrito = {prod: 0 for prod in MENU.keys()}
            st.session_state.pedido_popup = nuevo_pedido
            st.rerun()

    # 5) Seguimiento en vivo abajo
    intervalo_seguimiento = REFRESH_SEGUIMIENTO_ESTUDIANTE if st.session_state.mis_pedidos else None

    @st.fragment(run_every=intervalo_seguimiento)
    def seccion_seguimiento_vivo():
        if st.session_state.mis_pedidos:
            st.markdown("---")
            col_titulo, col_btn = st.columns([4, 1])
            with col_titulo:
                st.markdown("### 📍 Seguimiento en Vivo de tu Pedido")
            with col_btn:
                if st.button("🔄 Actualizar", key="btn_refresh_est"):
                    st.rerun()

            for pid in reversed(st.session_state.mis_pedidos):
                pedido_actual = next((o for o in db_orders if o["id"] == pid), None)
                if pedido_actual:
                    mostrar_tarjeta_seguimiento(pedido_actual, permitir_acciones=True)

    seccion_seguimiento_vivo()

    st.markdown("---")
    with st.expander("🔍 Consultar otro pedido por código"):
        busqueda_id = st.text_input("Ingresa el código de pedido (ej. ORD-1234):").strip().upper()
        if busqueda_id:
            pedido_encontrado = next((o for o in db_orders if o["id"] == busqueda_id), None)
            if pedido_encontrado:
                mostrar_tarjeta_seguimiento(pedido_encontrado, permitir_acciones=True)
            else:
                st.error("Código de pedido no encontrado.")

    with st.expander("⭐ Evaluar Prototipo (Validación Piloto ULS)"):
        st.caption("Ayúdanos respondiendo estas 3 preguntas breves tras probar el sistema de pedidos:")
        with st.form("form_encuesta_piloto", clear_on_submit=True):
            eval_nombre = st.text_input("Tu nombre (opcional):", placeholder="Ej. Estudiante ULS")
            eval_facilidad = st.slider("1. ¿Qué tan fácil fue realizar el pedido? (1 = Muy difícil, 5 = Muy fácil)", 1, 5, 5)
            eval_ahorro = st.radio(
                "2. ¿Sientes que este sistema reduciría tu tiempo de espera en fila?",
                ["Sí, considerablemente", "Sí, un poco", "No noté diferencia"],
                horizontal=True
            )
            eval_comentario = st.text_input("3. ¿Qué mejorarías o qué te costó entender? (opcional):")
            enviar_eval = st.form_submit_button("Enviar Evaluación", type="primary")
            if enviar_eval:
                db_surveys.append({
                    "hora": ahora_chile().strftime("%H:%M:%S"),
                    "usuario": eval_nombre.strip() if eval_nombre.strip() else "Anónimo",
                    "facilidad_1_a_5": eval_facilidad,
                    "percepcion_ahorro": eval_ahorro,
                    "comentario": eval_comentario.strip()
                })
                st.success("✅ ¡Muchas gracias! Tu evaluación quedó registrada para el estudio.")

# ==========================================
# VISTA 2: CAJA (APROBACIÓN Y STOCK)
# ==========================================
elif modo == "💵 Caja (Aprobación y Stock)":
    if not verificar_login_personal():
        st.stop()

    st.title("💵 Panel de Caja — Validación de Stock y Cobro")
    st.caption("1) Aprueba la disponibilidad de stock. 2) Una vez pagado (digital o en efectivo), el pedido pasa automáticamente a Cocina.")

    # Control de stock disponible
    with st.expander("🛑 Control de Stock del Día (Activar / Detener Ventas)", expanded=True):
        st.caption("Apaga un producto cuando ya no queden porciones disponibles para bloquear nuevas solicitudes.")
        cols_stock = st.columns(len(MENU))
        for idx, prod in enumerate(MENU.keys()):
            with cols_stock[idx]:
                esta_agotado = config_op["productos_agotados"].get(prod, False)
                disponible = st.toggle(
                    f"{prod}",
                    value=(not esta_agotado),
                    key=f"caja_stock_toggle_{prod}"
                )
                nuevo_agotado = not disponible
                if nuevo_agotado != esta_agotado:
                    config_op["productos_agotados"][prod] = nuevo_agotado
                    st.rerun()
                if nuevo_agotado:
                    st.error("🚫 Sin stock")
                else:
                    st.success("✅ Con stock")

    @st.fragment(run_every=REFRESH_OPERACION)
    def panel_aprobacion_caja():
        pendientes_aprob = [o for o in db_orders if o["estado"] == "Pendiente aprobación"]
        esperando_pago = [o for o in db_orders if o["estado"] == "Aprobado - Pendiente de Pago"]
        enviados_cocina = [o for o in db_orders if o["estado"] in ["En preparación", "Listo", "Cliente en mesón", "Entregado"]]

        c_m1, c_m2, c_m3, c_r = st.columns([1.6, 1.6, 1.6, 1])
        with c_m1:
            st.metric("1. Por Aprobar Stock", len(pendientes_aprob))
        with c_m2:
            st.metric("2. Esperando Pago", len(esperando_pago))
        with c_m3:
            st.metric("3. Pagados en Cocina", len(enviados_cocina))
        with c_r:
            if st.button("🔄 Refrescar", key="btn_refresh_caja"):
                st.rerun()

        tab_aprobar, tab_cobrar = st.tabs([
            f"📥 1. Solicitudes por Aprobar ({len(pendientes_aprob)})",
            f"💳 2. Aprobados Esperando Pago ({len(esperando_pago)})"
        ])

        with tab_aprobar:
            if not pendientes_aprob:
                st.info("No hay solicitudes nuevas pendientes de revisión de stock.")
            else:
                for order in pendientes_aprob:
                    with st.container(border=True):
                        col_inf, col_acc = st.columns([3, 1.7])
                        with col_inf:
                            st.markdown(f"#### 🧾 `{order['id']}` — 👤 **{order['cliente']}** | ⏰ Franja: `{order['franja']}`")
                            st.write(f"**Pedido:** {order['detalle_productos']} ({order.get('cantidad_total', 1)} cupo/s)")
                            st.caption(f"Solicitud: {order['hora_registro']} | Medio elegido: **{order['pago']}** | Total: **{formato_clp(order['precio'])}**")
                        with col_acc:
                            if st.button(
                                "✅ Aprobar Stock",
                                key=f"caja_aprobar_{order['id']}",
                                type="primary",
                                use_container_width=True
                            ):
                                actualizar_estado_pedido(order, "Aprobado - Pendiente de Pago")
                                st.toast(f"Pedido {order['id']} aprobado. Habilitado para pago del cliente.")
                                st.rerun()

                            if st.button(
                                "❌ Rechazar (Sin Stock)",
                                key=f"caja_rechazar_{order['id']}",
                                use_container_width=True
                            ):
                                actualizar_estado_pedido(order, "Descartado", motivo_descarte="Rechazado en caja")
                                st.toast(f"Pedido {order['id']} rechazado. Cupos liberados.")
                                st.rerun()

        with tab_cobrar:
            if not esperando_pago:
                st.info("No hay pedidos aprobados pendientes de pago.")
            else:
                for order in esperando_pago:
                    with st.container(border=True):
                        c_p1, c_p2 = st.columns([3, 1.8])
                        with c_p1:
                            st.markdown(f"#### 💳 `{order['id']}` — 👤 **{order['cliente']}** | ⏰ Franja: `{order['franja']}`")
                            st.write(f"**Detalle:** {order['detalle_productos']} | Total: **{formato_clp(order['precio'])}** ({order['pago']})")
                            if order["pago"] == "Efectivo en Caja":
                                st.caption("💵 Esperando que el estudiante se acerque a pagar en efectivo en Caja.")
                            else:
                                st.caption("📱 Esperando que el estudiante confirme el pago digital desde su celular.")
                        with c_p2:
                            etiqueta_cobro = "💵 Registrar Pago Efectivo" if order["pago"] == "Efectivo en Caja" else "✅ Confirmar Pago Manual"
                            if st.button(
                                etiqueta_cobro,
                                key=f"caja_cobrar_{order['id']}",
                                type="primary",
                                use_container_width=True
                            ):
                                exito, tx_id = procesar_pago(order["pago"], order["precio"])
                                if exito:
                                    order["tx_id"] = tx_id
                                    actualizar_estado_pedido(order, "En preparación")
                                    st.toast(f"Pago registrado ({tx_id}). Pedido enviado a Cocina.")
                                    st.rerun()

                            if st.button(
                                "❌ Anular por No Pago",
                                key=f"caja_anular_impago_{order['id']}",
                                use_container_width=True
                            ):
                                actualizar_estado_pedido(order, "Descartado", motivo_descarte="Anulado por falta de pago")
                                st.rerun()

    panel_aprobacion_caja()

# ==========================================
# VISTA 3: COCINA (PREPARACIÓN Y ENTREGA - ACCESIBLE)
# ==========================================
elif modo == "🍳 Cocina (Preparación y Entrega)":
    if not verificar_login_personal():
        st.stop()

    # Estilos de alta visibilidad y botones extra grandes para personal de cocina
    st.markdown("""
        <style>
        /* Botones principales (Entregar / Abrir Escáner - Verde alto contraste) */
        div.stButton > button[kind="primary"] {
            background-color: #198754 !important;
            border: 3px solid #146c43 !important;
            color: #ffffff !important;
            font-size: 21px !important;
            font-weight: 800 !important;
            min-height: 68px !important;
            border-radius: 12px !important;
            letter-spacing: 0.4px !important;
        }
        div.stButton > button[kind="primary"]:hover {
            background-color: #157347 !important;
        }

        /* Botones secundarios grandes (Marcar Listo / Cerrar Escáner) */
        div.stButton > button[kind="secondary"] {
            background-color: #e67e22 !important;
            border: 3px solid #ca6f1e !important;
            color: #ffffff !important;
            font-size: 20px !important;
            font-weight: 800 !important;
            min-height: 64px !important;
            border-radius: 12px !important;
        }
        div.stButton > button[kind="secondary"]:hover {
            background-color: #d35400 !important;
        }

        /* Textos más grandes y claros en tarjetas de pedidos */
        .cocina-titulo-pedido {
            font-size: 26px;
            font-weight: 800;
            margin-bottom: 4px;
            line-height: 1.2;
        }
        .cocina-detalle-comida {
            font-size: 23px;
            font-weight: 700;
            color: #1a202c;
            background-color: #f8f9fa;
            padding: 10px 14px;
            border-radius: 8px;
            border-left: 6px solid #0d6efd;
            margin: 8px 0;
        }
        .cocina-subdato {
            font-size: 17px;
            color: #4a5568;
            font-weight: 600;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("# 🍳 Pantalla de Cocina")
    st.markdown("#### Instrucciones rápidas: **1)** Prepara el pedido y toca **🔔 MARCAR LISTO**. **2)** Cuando llegue el estudiante, toca **🤝 ENTREGAR PEDIDO**.")

    # Mostrar alerta si se acaba de escanear un QR
    if st.session_state.ultimo_resultado_qr is not None:
        tipo_res, msg_res = st.session_state.ultimo_resultado_qr
        st.session_state.ultimo_resultado_qr = None
        if tipo_res == "success":
            st.success(msg_res)
        elif tipo_res == "warning":
            st.warning(msg_res)
        elif tipo_res == "info":
            st.info(msg_res)
        else:
            st.error(msg_res)

    @st.fragment(run_every=REFRESH_OPERACION)
    def panel_cocina_vivo():
        clientes_esperando = [o for o in db_orders if o["estado"] == "Cliente en mesón"]
        en_preparacion = [o for o in db_orders if o["estado"] == "En preparación"]
        listos_sin_llegar = [o for o in db_orders if o["estado"] == "Listo"]
        historial_cerrados = [o for o in db_orders if o["estado"] in ["Entregado", "Descartado"]]

        # Indicadores grandes y directos arriba
        c1, c2, c3, c_ref = st.columns([1.6, 1.6, 1.6, 1])
        with c1:
            st.metric("🚨 ESPERANDO EN MESÓN", len(clientes_esperando))
        with c2:
            st.metric("👨‍🍳 POR PREPARAR", len(en_preparacion))
        with c3:
            st.metric("🔔 LISTOS PARA RETIRAR", len(listos_sin_llegar))
        with c_ref:
            st.write("")
            if st.button("🔄 Actualizar", key="btn_refresh_cocina", use_container_width=True):
                st.rerun()

        st.markdown("---")

        # =========================================================
        # BLOQUE 1: CLIENTES QUE YA LLEGARON A RETIRAR (PRIORIDAD)
        # =========================================================
        if clientes_esperando:
            st.error(f"🚨 ¡ATENCIÓN! Hay **{len(clientes_esperando)} persona(s)** esperando en el mesón para retirar:")
            for order in clientes_esperando:
                with st.container(border=True):
                    col_alerta, col_ent = st.columns([2.6, 1.4])
                    with col_alerta:
                        st.markdown(
                            f"<div class='cocina-titulo-pedido'>📣 {order['cliente']} — Pedido {order['id']}</div>",
                            unsafe_allow_html=True
                        )
                        st.markdown(
                            f"<div class='cocina-detalle-comida' style='border-left-color: #dc3545; background-color: #fff5f5;'>"
                            f"🍽️ ENTREGAR: {order['detalle_productos']}</div>",
                            unsafe_allow_html=True
                        )
                        st.markdown(
                            f"<div class='cocina-subdato'>⏰ Franja: {order['franja']} | Llegó al mesón: {order.get('hora_llegada_cliente', '-')}</div>",
                            unsafe_allow_html=True
                        )
                    with col_ent:
                        st.write("")
                        if st.button(
                            "🤝 ENTREGAR PEDIDO",
                            key=f"cocina_entregar_{order['id']}",
                            type="primary",
                            use_container_width=True
                        ):
                            actualizar_estado_pedido(order, "Entregado")
                            st.toast(f"✅ Pedido {order['id']} entregado a {order['cliente']}.")
                            st.rerun()
            st.markdown("---")

        # =========================================================
        # BLOQUE 2: PEDIDOS POR PREPARAR (ORDENADOS POR FRANJA)
        # =========================================================
        st.markdown("## 👨‍🍳 1. Pedidos por Preparar")
        if not en_preparacion:
            st.success("✅ No hay pedidos pendientes de preparación en este momento.")
        else:
            for slot in TIME_SLOTS:
                ordenes_slot = [o for o in en_preparacion if o["franja"] == slot]
                if ordenes_slot:
                    st.markdown(f"### ⏰ Horario de Retiro: **{slot}** ({len(ordenes_slot)} pedido/s)")
                    for order in ordenes_slot:
                        with st.container(border=True):
                            c_txt, c_btn = st.columns([2.6, 1.4])
                            with c_txt:
                                st.markdown(
                                    f"<div class='cocina-titulo-pedido'>📦 {order['id']} — 👤 {order['cliente']}</div>",
                                    unsafe_allow_html=True
                                )
                                st.markdown(
                                    f"<div class='cocina-detalle-comida'>🍽️ PREPARAR: {order['detalle_productos']}</div>",
                                    unsafe_allow_html=True
                                )
                                st.markdown(
                                    f"<div class='cocina-subdato'>Pagado a las {order.get('hora_pago', '-')}</div>",
                                    unsafe_allow_html=True
                                )
                            with c_btn:
                                st.write("")
                                if st.button(
                                    "🔔 MARCAR LISTO",
                                    key=f"cocina_listo_{order['id']}",
                                    type="secondary",
                                    use_container_width=True
                                ):
                                    actualizar_estado_pedido(order, "Listo")
                                    st.toast(f"🔔 Pedido {order['id']} listo para retirar.")
                                    st.rerun()

        st.markdown("---")

        # =========================================================
        # BLOQUE 3: PEDIDOS YA LISTOS ESPERANDO QUE LLEGUE EL ALUMNO
        # =========================================================
        st.markdown("## 🔔 2. Pedidos Listos (Esperando al Estudiante)")
        if not listos_sin_llegar:
            st.info("No hay pedidos listos esperando retiro.")
        else:
            for order in listos_sin_llegar:
                with st.container(border=True):
                    c_l1, c_l2 = st.columns([2.6, 1.4])
                    with c_l1:
                        st.markdown(
                            f"<div class='cocina-titulo-pedido'>🔔 {order['id']} — 👤 {order['cliente']}</div>",
                            unsafe_allow_html=True
                        )
                        st.markdown(
                            f"<div class='cocina-detalle-comida' style='border-left-color: #198754;'>"
                            f"🍽️ LISTO: {order['detalle_productos']}</div>",
                            unsafe_allow_html=True
                        )
                        st.markdown(
                            f"<div class='cocina-subdato'>⏰ Franja: {order['franja']} | Listo desde las {order.get('hora_listo', '-')}</div>",
                            unsafe_allow_html=True
                        )
                    with c_l2:
                        st.write("")
                        if st.button(
                            "🤝 ENTREGAR AHORA",
                            key=f"cocina_ent_man_{order['id']}",
                            type="primary",
                            use_container_width=True
                        ):
                            actualizar_estado_pedido(order, "Entregado")
                            st.toast(f"✅ Pedido {order['id']} entregado.")
                            st.rerun()

        with st.expander(f"📁 Ver Pedidos Ya Entregados Hoy ({len(historial_cerrados)})", expanded=False):
            if not historial_cerrados:
                st.info("Aún no hay pedidos entregados hoy.")
            else:
                for order in reversed(historial_cerrados):
                    st.write(f"✔️ **{order['id']} — {order['cliente']}** | {order['detalle_productos']} | Estado: **{order['estado']}** ({order['hora_entrega']})")

    panel_cocina_vivo()

    # =========================================================
    # ESCÁNER QR BAJO DEMANDA (CÁMARA APAGADA HASTA PULSAR BOTÓN)
    # =========================================================
    st.markdown("---")
    st.markdown("## 📷 Punto de Escaneo QR (Llegada de Estudiantes)")

    if not st.session_state.escaner_abierto:
        if st.button(
            "📷 ABRIR ESCÁNER QR",
            key="btn_abrir_escaner",
            type="primary",
            use_container_width=True
        ):
            st.session_state.escaner_abierto = True
            st.session_state.scanner_session_id += 1
            st.rerun()
    else:
        if st.button(
            "❌ CERRAR CÁMARA ESCÁNER",
            key="btn_cerrar_escaner",
            type="secondary",
            use_container_width=True
        ):
            st.session_state.escaner_abierto = False
            st.rerun()

        with st.container(border=True):
            col_cam, col_man = st.columns([1.3, 1])
            with col_cam:
                qr_leido_camara = escaner_qr_nativo(
                    key=f"qr_cam_v2_{st.session_state.scanner_session_id}",
                    default=None
                )
                if qr_leido_camara:
                    tipo_res, msg_res = procesar_escaneo_qr_totem(qr_leido_camara)
                    st.session_state.ultimo_resultado_qr = (tipo_res, msg_res)
                    st.session_state.escaner_abierto = False
                    st.rerun()

            with col_man:
                st.markdown("#### Lector Óptico / Ingreso Manual:")
                token_manual = st.text_input(
                    "Código leído:",
                    placeholder="DOMEYKO-QR|ORD-1234|TX-XXXXXX",
                    key="input_lector_cocina"
                ).strip()
                if st.button(
                    "✅ VALIDAR CÓDIGO QR",
                    key="btn_validar_cocina",
                    type="primary",
                    use_container_width=True
                ):
                    if token_manual:
                        tipo_res, msg_res = procesar_escaneo_qr_totem(token_manual)
                        st.session_state.ultimo_resultado_qr = (tipo_res, msg_res)
                        if tipo_res == "success":
                            st.session_state.escaner_abierto = False
                        st.rerun()

# ==========================================
# VISTA 4: MÉTRICAS Y EXPORTACIÓN
# ==========================================
else:
    if not verificar_login_personal():
        st.stop()

    st.title("📊 Análisis de Datos y Trazabilidad del Prototipo")
    st.markdown("Registro cuantitativo de órdenes por etapa (Solicitud → Aprobación → Pago → Cocina → QR → Entrega) y encuestas piloto.")

    st.subheader("1. Tiempos de Operación por Pedido")
    if not db_orders:
        st.info("Aún no hay datos recolectados. Registra algunos pedidos desde la vista de estudiante.")
    else:
        registros_con_metricas = []
        for o in db_orders:
            fila = dict(o)
            fila["min_aprobacion_caja"] = calcular_minutos_diferencia(o.get("hora_registro"), o.get("hora_aprobacion"))
            fila["min_confirmacion_pago"] = calcular_minutos_diferencia(o.get("hora_aprobacion"), o.get("hora_pago"))
            fila["min_preparacion_cocina"] = calcular_minutos_diferencia(o.get("hora_pago"), o.get("hora_listo"))
            fila["min_espera_retiro"] = calcular_minutos_diferencia(o.get("hora_llegada_cliente"), o.get("hora_entrega"))
            fila["min_total_atencion"] = calcular_minutos_diferencia(o.get("hora_registro"), o.get("hora_entrega"))
            registros_con_metricas.append(fila)

        df = pd.DataFrame(registros_con_metricas)
        st.dataframe(df, use_container_width=True)

        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar Reporte de Tiempos (CSV)",
            data=csv_data,
            file_name=f"reporte_cafeteria_{ahora_chile().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            type="primary"
        )

    st.markdown("---")
    st.subheader("2. Resultados de Encuesta Piloto (Usabilidad)")
    if not db_surveys:
        st.info("Aún no hay respuestas de encuesta registradas desde la vista del estudiante.")
    else:
        df_surveys = pd.DataFrame(db_surveys)
        promedio_facilidad = round(df_surveys["facilidad_1_a_5"].mean(), 2)
        st.metric("Promedio Facilidad de Uso (1 a 5)", f"{promedio_facilidad} / 5.0", f"{len(df_surveys)} respuestas")
        st.dataframe(df_surveys, use_container_width=True)

        csv_surveys = df_surveys.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar Encuestas Piloto (CSV)",
            data=csv_surveys,
            file_name=f"encuestas_piloto_{ahora_chile().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )