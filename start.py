#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A2K Digital Studio — Bot de Ventas de SISTEMAS (@zync_shop_bot)
Vende: POS/inventarios, landing pages, asistentes virtuales, bots de voz,
automatizaciones n8n. Cerebro DeepSeek + Flask keep-alive + /mensajes (voz).

v2.0 — Flujo de venta con licencia REAL:
  1) Aria conversa y detecta qué sistema quiere el cliente y en qué dispositivo (PC/celular)
  2) El cliente envía el capture de pago → se reenvía al admin con botón de confirmación
  3) El admin confirma → el bot crea la licencia en el License Engine (serie real)
     y entrega al cliente el link oficial de entrega con su código
  4) Licencia vinculada al dispositivo (anti-fraude) con migración gratuita vía panel
"""
import os, time, threading, logging, base64
import telebot, requests
from flask import Flask, jsonify, request
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.environ.get('BOT_TOKEN')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
NOTIF_KEY = os.environ.get('NOTIF_KEY', '')
LICENSE_ADMIN_KEY = os.environ.get('LICENSE_ADMIN_KEY', '')  # clave del License Engine
ADMIN_CHAT = int(os.environ.get('ADMIN_CHAT', '7579580673'))  # chat de Abigail
ENGINE = 'https://a2k-license-engine.shoppingelectronics3112.workers.dev'

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)

clientes_mensajes = []
msg_counter = [0]
BOT_THREAD = None

app = Flask(__name__)

@app.route('/')
@app.route('/health')
def health():
    global BOT_THREAD
    activo = bool(BOT_THREAD and BOT_THREAD.is_alive())
    if not activo:
        try:
            iniciar_bot(); activo = True
        except Exception as e:
            log.error(f"reinicio fallo: {e}")
    return jsonify({"status": "ok", "service": "A2K Systems Bot", "bot_activo": activo}), 200

@app.route('/mensajes')
def mensajes():
    if not NOTIF_KEY or request.args.get('key') != NOTIF_KEY:
        return jsonify({"ok": False, "error": "no autorizado"}), 403
    after = request.args.get('after', 0, type=int)
    return jsonify({"ok": True,
                    "bot_activo": bool(BOT_THREAD and BOT_THREAD.is_alive()),
                    "mensajes": [m for m in clientes_mensajes if m['id'] > after]})

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)), debug=False)

SYSTEM_PROMPT = """Eres "Aria", la vendedora estrella de A2K Digital Studio por Telegram. Vendes SISTEMAS y servicios digitales para empresas en Venezuela y LatAm. Profesional, educada, persuasiva, honesta. Español venezolano natural, 1-3 emojis, máximo 120 palabras.

TU MÉTODO DE VENTA (siempre):
1. ABRE: saluda y haz UNA pregunta abierta ("¿qué tipo de negocio manejas?").
2. DESCUBRE: qué necesita (vender más, ordenar inventario, atender clientes 24/7, presencia web).
3. PRESENTA la solución exacta de catálogo con su precio.
4. CONVENCE: manejo de objeciones — "está caro" → valor (paga una vez, es suyo de por vida, soporte incluido, multiplica ventas, INCLUYE el Libro Fiscal para el contador); "lo pienso" → cupos de implementación limitados; "no soy tecnológico" → lo instalamos y enseñamos TODO.
5. CIERRA asumiendo: "¿con cuál arrancamos: Bodega o el de tu rubro?".

PREGUNTA CLAVE ANTES DE COBRAR: cuando el cliente diga que sí quiere comprar, pregunta SIEMPRE: "¿Lo vas a usar en una PC/laptop o en tu celular Android? Cada licencia es exclusiva para un tipo de dispositivo."

PAGO: Métodos: Zelle, bolívares a tasa USDT (P2P), Binance USDT. Cuando el cliente diga que ya pagó, dile: "Perfecto, envíame aquí mismo el capture/foto del comprobante y en cuanto se confirme te entrego tu licencia con el link de instalación. Es automático y rápido."

LICENCIA Y ENTREGA (informa con orgullo):
- Licencia permanente del plan contratado, con soporte e instalación incluidos el primer año.
- Se vincula al primer dispositivo donde se active (protección anti-fraude).
- Si el cliente cambia de equipo, la migración es GRATIS (solo lo pide por WhatsApp).
- Cliente con licencia activa: su SEGUNDA licencia cuesta solo $18 (en vez de $30).
- ¿Ya tienes el Plan Básico y quieres facturación fiscal? Upgrade al Plan Pro por $125 (solo pagas la diferencia).

CATÁLOGO OFICIAL — SISTEMAS (todos en Plan Básico $30 USD c/u, licencia de por vida + soporte + Libro Fiscal interno incluido):
- 💈 Barbería Pro — turnos, servicios, caja, reportes
- 💅 Nail Studio Pro — agenda, clientas, materiales, precios
- 📦 Bodega Pro — POS, inventario, fiados, proveedores
- 💊 Farmacia Pro Plus — ventas, inventario, vencimientos, multi-país
- 🛒 Mercado Logic Pro — POS industrial para abastos
- 🏍️ MotoTaller Pro — repuestos, órdenes, clientes
- 🍎 Frutería Pro — POS con merma y fiados
- 🔧 Ferretería A2K Pro — inventario por familias, cotizaciones
- 🦷 Zync Dental Pro — clínica dental, insumos, citas
- 🍔 A2K Comandas — comandas para restaurantes
- 🍞 Panadería Pro — producción, materia prima, ventas y fiados para panaderías/pastelerías
- 🤖 Recepcionista AI — atiende clientes 24/7 por WhatsApp/web

PLANES (presenta siempre la selección; deja que el cliente decida):
- 📦 Plan Básico — $30 de por vida: sistema completo (inventario, ventas, fiados, caja, reportes) + Libro Fiscal interno con IVA/IGTF desglosados para el contador. NO emite facturas fiscales legales.
- 🏛️ Plan Pro — $150 de por vida: TODO lo del Básico + facturación electrónica oficial SENIAT conectada a la imprenta autorizada que el cliente elija (The Factory HKA, Unidigital, 421 u otra), contrato de licencia firmado digitalmente, libros de compras y ventas oficiales exportables y modo de contingencia automática. Requisito del cliente: RIF activo y designación de la imprenta ante el SENIAT — A2K lo guía paso a paso; no es automático ni instantáneo.
- 🔧 Mantenimiento — $22.50/año desde el segundo año: soporte prioritario y actualizaciones.
- 🔄 Upgrade: del Básico al Pro pagas solo $125.

FUNCIÓN ESTRELLA — LIBRO FISCAL (incluida en el Plan Básico, sin costo extra):
Cada sistema lleva SOLO los ingresos y egresos de tu negocio: cada venta, compra, gasto y fiado queda registrado al instante. A fin de mes NO sacas cuentas ni llevas bolsas de facturas: entras al módulo "Libro Fiscal", ves el IVA desglosado (16%), el IGTF (3%) de tus cobros en divisas, tus compras, cuentas por cobrar y por pagar — y con UN TOQUE imprimes el PDF o descargas el Excel para tu contador. Organízate ya desde tu sistema y haz tus declaraciones lo más rápido posible, sin perder ni obviar nada. (Activa hoy en la versión PC/web; llega a la app Android en su próxima actualización, gratis.) La EMISIÓN de facturas fiscales legales ante el SENIAT es exclusiva del Plan Pro.

CONTROL DE EMPLEADOS: crea un usuario para cada empleado y bloquea las secciones que no debe tocar (ej: que el cajero no vea costos ni reportes). Así proteges tu negocio de pérdidas y desconfianza.

MULTI-PAÍS: los sistemas funcionan en cualquier país — tú configuras la moneda y la tasa, y trabajas online u offline.

SERVICIOS A MEDIDA (cotización según proyecto):
- 🌐 Landing pages profesionales
- 🤖 Asistentes virtuales para cualquier empresa
- 🎙️ Bots de voz
- ⚙️ Automatizaciones n8n (flujos de ventas, respaldos, publicaciones)

REGLAS DE ORO:
- Precios SOLO del catálogo. Plan Básico: $30 USD c/u ($18 la segunda licencia). Plan Pro: $150 (upgrade desde Básico: $125). Mantenimiento: $22.50/año desde el año 2. Servicios a medida: cotizar, nunca inventar precio.
- Soporte e instalación incluidos. Licencia de por vida.
- Los sistemas son apps que el cliente usa en su PC o celular Android.
- Si pide algo fuera de catálogo o hablar con humano: asesor WhatsApp wa.me/584164117331
- Nunca mientas sobre capacidades ni tiempos.
- Tú NO entregas licencias ni links directamente: cuando llegue el comprobante, lo validan y se entrega automático. Dile eso al cliente.
- ⚠️ REGLA DE LINKS (inquebrantable): NUNCA escribas ni inventes URLs. El ÚNICO link que das al cliente es el "Link oficial de entrega" que te llega al confirmar el pago. Si te preguntan dónde descargar antes de pagar, diles: "al pagar recibes tu link oficial con tu código, listo para instalar en minutos". NUNCA links de github.com, nunca links "de ejemplo"."""

# ── Estado de ventas pendientes (chat del cliente → lo que quiere comprar) ──
# producto: id del sistema · plataforma: 'pc' | 'android' | None
pendientes = {}   # chat_id -> {"producto": str|None, "plataforma": str|None, "nombre": str}
esperando_plat = {}  # chat_id que debe responder PC/celular antes de generar

PRODUCTOS_KW = {
    'barberia': ['barbería', 'barberia', 'barbero', 'peluquería', 'peluquero', 'estilista'],
    'nail': ['nail', 'uñas', 'manicure', 'manicura', 'pedicure', 'pedicura', 'spa de uñas'],
    'bodega': ['bodega', 'bodegón', 'bodegon', 'minimarket', 'mini market', 'licorería'],
    'farmacia': ['farmacia', 'farmacias', 'droguería'],
    'mercado': ['mercado logic', 'abastos', 'supermercado', 'mercado'],
    'motos': ['mototaller', 'moto taller', 'repuestos de moto', 'taller de motos'],
    'fruteria': ['frutería', 'fruteria', 'verdulería', 'frutas y verduras'],
    'ferreteria': ['ferretería', 'ferreteria'],
    'dental': ['dental', 'dentista', 'odontología', 'odontologia', 'ortodoncia', 'clínica dental'],
    'comandas': ['comandas', 'restaurante', 'menú digital', 'meseros', 'comida rápida'],
    'recepcionista': ['recepcionista', 'asistente virtual', 'atienda clientes 24', 'secretaria virtual'],
    'zync': ['zync electronics'],
    'synthtrade': ['synthtrade'],
    'fiadospro': ['fiadospro', 'control de fiados', 'cobrar fiados'],
    'panaderia': ['panadería', 'panaderia', 'panadero', 'pastelería', 'pasteleria', 'repostería', 'reposteria', 'cafetería', 'cafeteria'],
}
NOMBRES_SISTEMAS = {
    'barberia': 'Barbería Pro', 'nail': 'Nail Studio Pro', 'bodega': 'Bodega Pro v9',
    'farmacia': 'Farmacia Pro', 'mercado': 'Mercado Logic Pro', 'motos': 'MotoTaller Pro',
    'fruteria': 'Frutería Pro', 'ferreteria': 'Ferretería Zync Pro', 'dental': 'Zync Dental Pro',
    'comandas': 'A2K Comandas', 'recepcionista': 'Recepcionista AI', 'zync': 'ZYNC Electronics',
    'synthtrade': 'SynthTrade Pro', 'fiadospro': 'FiadosPro', 'panaderia': 'Panadería Pro',
}
PLATAFORMA_LABEL = {'pc': '💻 PC / Laptop', 'android': '📱 Celular Android'}

conversations = {}
bot = telebot.TeleBot(TELEGRAM_TOKEN)

def _responder(m, texto):
    try:
        bot.reply_to(m, texto, parse_mode='Markdown')
    except Exception:
        try:
            bot.reply_to(m, texto)
        except Exception as e2:
            log.error(f"envio fallo: {e2}")

def _enviar(chat_id, texto):
    try:
        bot.send_message(chat_id, texto, parse_mode='Markdown')
    except Exception:
        try:
            bot.send_message(chat_id, texto)
        except Exception as e2:
            log.error(f"envio fallo: {e2}")

def ask_deepseek(chat_id, text):
    hist = conversations.get(chat_id, [])
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + hist[-14:] + [{"role": "user", "content": text}]
    try:
        r = requests.post("https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": msgs, "temperature": 0.7, "max_tokens": 300},
            timeout=45)
        if r.status_code == 200:
            ans = r.json()['choices'][0]['message']['content'].strip()
            hist += [{"role": "user", "content": text}, {"role": "assistant", "content": ans}]
            conversations[chat_id] = hist[-16:]
            return ans
        return "😓 Problemita técnico. ¿Repetirme tu mensaje, por favor? 🙏"
    except Exception as e:
        log.error(f"DeepSeek: {e}")
        return "😓 Problemita técnico. ¿Repetirme tu mensaje, por favor? 🙏"

# ── Detección de intención (producto + dispositivo) ──
def detectar_producto(texto):
    t = texto.lower()
    for prod, kws in PRODUCTOS_KW.items():
        if any(k in t for k in kws):
            return prod
    return None

def detectar_plataforma(texto):
    t = texto.lower()
    pc_words = ['pc', 'laptop', 'computadora', 'computador', 'escritorio', 'windows', 'notebook', 'equipo']
    mob_words = ['celular', 'android', 'móvil', 'movil', 'teléfono', 'telefono', 'phone', 'moto g', 'samsung', 'xiaomi']
    es_pc = any(w in t for w in pc_words)
    es_mob = any(w in t for w in mob_words)
    if es_mob and not es_pc: return 'android'
    if es_pc and not es_mob: return 'pc'
    return None

def estado_cliente(chat_id):
    return pendientes.setdefault(chat_id, {"producto": None, "plataforma": None, "nombre": ""})

# ── Crear licencia en el Engine y entregar ──
def crear_licencia_engine(producto, plataforma, cliente, telefono=''):
    if not LICENSE_ADMIN_KEY:
        return None, "LICENSE_ADMIN_KEY no configurada en Render"
    try:
        r = requests.post(f"{ENGINE}/crear",
            headers={"Content-Type": "application/json", "X-Admin-Key": LICENSE_ADMIN_KEY},
            json={"product": producto, "type": "pro", "cliente": cliente,
                  "telefono": telefono, "plataforma": plataforma or ''},
            timeout=30)
        d = r.json()
        if d.get('ok'):
            return d, None
        return None, d.get('error', 'error desconocido del engine')
    except Exception as e:
        return None, str(e)

def entregar_licencia(cliente_chat, admin_msg_id=None):
    """Genera la licencia con lo que hay en pendientes y se la entrega al cliente."""
    st = estado_cliente(cliente_chat)
    producto = st.get('producto')
    plataforma = st.get('plataforma')

    if not producto:
        _enviar(ADMIN_CHAT, "⚠️ No sé qué sistema quiere el cliente. Pregúntale y vuelve a confirmar.")
        return
    if not plataforma:
        # El admin confirmó pero falta el dispositivo → se lo preguntamos al cliente
        esperando_plat[cliente_chat] = True
        _enviar(cliente_chat,
            "🎉 *¡Tu pago fue confirmado!* Antes de generar tu licencia, dime una cosa:\n\n"
            "¿La vas a usar en una *PC/laptop* 💻 o en tu *celular Android* 📱?\n\n"
            "Cada licencia es exclusiva para un tipo de dispositivo (así protegemos tu compra).")
        _enviar(ADMIN_CHAT, "⏳ Le pregunté al cliente si es PC o celular. En cuanto responda, se genera la licencia automático.")
        return

    nombre_cliente = st.get('nombre') or 'Cliente'
    lic, err = crear_licencia_engine(producto, plataforma, nombre_cliente)
    if not lic:
        _enviar(ADMIN_CHAT, f"❌ Error creando licencia: {err}")
        return

    link = lic.get('link') or f"{ENGINE}/p/{lic['key']}"
    nombre_sistema = NOMBRES_SISTEMAS.get(producto, producto)
    plat_txt = PLATAFORMA_LABEL.get(plataforma, 'tu dispositivo')

    _enviar(cliente_chat,
        f"🎉 *¡Tu licencia está lista!*\n\n"
        f"📦 *{nombre_sistema}* — {plat_txt}\n"
        f"🔑 Código: *{lic['key']}*\n\n"
        f"🔗 *Link oficial de entrega:*\n{link}\n\n"
        f"Ábrelo desde tu {plat_txt.split(' ',1)[1] if ' ' in plat_txt else 'dispositivo'}, copia el código y sigue los pasos — quedará activo en minutos.\n\n"
        f"🛡️ Tu licencia es *permanente* y queda vinculada a tu equipo. Si algún día cambias de dispositivo, la migramos *gratis*.\n"
        f"💜 Y recuerda: tu *segunda licencia* cuesta solo *$18*.\n\n"
        f"¿Dudas con la instalación? Aquí estoy. 😊")
    _enviar(ADMIN_CHAT,
        f"✅ Licencia entregada\nCliente: {nombre_cliente}\nSistema: {nombre_sistema} ({plataforma})\nCódigo: {lic['key']}")
    pendientes.pop(cliente_chat, None)
    esperando_plat.pop(cliente_chat, None)

# ── Handlers ──
@bot.message_handler(commands=['start'])
def welcome(m):
    # Capturar fuente de procedencia (?start=grp_...) para saber qué grupo trae clientes
    _partes = (m.text or '').split(maxsplit=1)
    if len(_partes) > 1:
        estado_cliente(m.chat.id)["fuente"] = _partes[1][:60]
    nombre = f" {m.from_user.first_name}" if m.from_user and m.from_user.first_name else ""
    estado_cliente(m.chat.id)["nombre"] = (m.from_user.first_name or "Cliente")[:40]
    _responder(m,
        f"🚀 *¡Bienvenido a A2K Digital Studio{nombre}!*\n\n"
        "Creamos los *sistemas y asistentes digitales* que hacen crecer negocios: "
        "puntos de venta, inventarios, páginas web, asistentes virtuales y automatizaciones. 🤖\n\n"
        "Tenemos un sistema listo para *cada rubro* — y si necesitas algo a tu medida, lo construimos.\n\n"
        "¿Qué tipo de negocio tienes o qué quieres lograr? Escríbeme con confianza: "
        "aquí no hay comandos ni botones raros — te leo y te respondo como una asesora real. 😎")

@bot.message_handler(content_types=['photo'])
def on_photo(m):
    """Capture de pago → reenviar al admin con botones de confirmación."""
    st = estado_cliente(m.chat.id)
    st["nombre"] = (m.from_user.first_name or "Cliente")[:40]

    caption = m.caption or ''
    prod = detectar_producto(caption)
    plat = detectar_plataforma(caption)
    if prod: st["producto"] = prod
    if plat: st["plataforma"] = plat

    nombre_sistema = NOMBRES_SISTEMAS.get(st["producto"], '❓ (preguntar cuál)')
    plat_txt = PLATAFORMA_LABEL.get(st["plataforma"], '❓ (preguntar PC/celular)')

    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("✅ PAGO CONFIRMADO — GENERAR LICENCIA", callback_data=f"okpay:{m.chat.id}"),
        telebot.types.InlineKeyboardButton("❌ Rechazar", callback_data=f"nopay:{m.chat.id}")
    )
    try:
        bot.send_photo(ADMIN_CHAT, m.photo[-1].file_id,
            caption=(f"💰 *CAPTURE DE PAGO*\n"
                     f"👤 Cliente: {st['nombre']} (chat `{m.chat.id}`)\n"
                     f"📍 Fuente: {st.get('fuente', '(directo)')}\n"
                     f"📦 Sistema detectado: {nombre_sistema}\n"
                     f"📱💻 Dispositivo: {plat_txt}\n"
                     f"📝 Caption: {caption[:200] or '—'}\n\n"
                     f"Confirma solo si el dinero ya está en tu cuenta."),
            parse_mode='Markdown', reply_markup=markup)
        _responder(m,
            "📩 ¡Recibido! Ya pasé tu comprobante a validación.\n\n"
            "En cuanto se confirme tu pago te entrego *tu licencia con el link de instalación* aquí mismo. "
            "Normalmente es cuestión de minutos. 🚀")
    except Exception as e:
        log.error(f"reenvio admin fallo: {e}")
        _responder(m, "📩 Recibí tu comprobante. Te confirmo enseguida. 🙏")

@bot.callback_query_handler(func=lambda c: c.data.startswith(('okpay:', 'nopay:')))
def on_pago_decision(c):
    accion, cliente_chat = c.data.split(':', 1)
    cliente_chat = int(cliente_chat)
    if c.from_user.id != ADMIN_CHAT:
        bot.answer_callback_query(c.id, "⛔ Solo la admin confirma pagos.")
        return
    try:
        bot.edit_message_reply_markup(ADMIN_CHAT, c.message.message_id, reply_markup=None)
    except Exception:
        pass
    bot.answer_callback_query(c.id, "Procesado ✓")

    if accion == 'okpay':
        entregar_licencia(cliente_chat)
    else:
        _enviar(cliente_chat,
            "😔 No logramos confirmar tu pago todavía.\n\n"
            "Si ya pagaste, envíanos el comprobante por aquí de nuevo o escríbenos a wa.me/584164117331 "
            "y lo revisamos al momento. 🙏")
        _enviar(ADMIN_CHAT, "❌ Pago rechazado — se avisó al cliente para que lo revise.")

@bot.message_handler(content_types=['text'])
def on_text(m):
    chat_id, text = m.chat.id, m.text.strip()
    st = estado_cliente(chat_id)
    st["nombre"] = (m.from_user.first_name or st["nombre"] or "Cliente")[:40]

    if not text.startswith('/'):
        nid = int(time.time() * 1000)
        msg_counter[0] = max(nid, msg_counter[0] + 1)
        clientes_mensajes.append({"id": msg_counter[0],
            "usuario": (m.from_user.first_name or "Cliente")[:30],
            "texto": text[:500], "hora": datetime.now().strftime('%H:%M:%S')})
        del clientes_mensajes[:-100]

        # ¿Es respuesta a "¿PC o celular?" tras pago confirmado?
        if esperando_plat.get(chat_id):
            plat = detectar_plataforma(text)
            if plat:
                st["plataforma"] = plat
                esperando_plat.pop(chat_id, None)
                entregar_licencia(chat_id)
                return

        # Detección normal de intención (la confirmación siempre la da el admin)
        prod = detectar_producto(text)
        plat = detectar_plataforma(text)
        if prod: st["producto"] = prod
        if plat: st["plataforma"] = plat
    else:
        text = text.lstrip('/').replace('_', ' ')
        if text.lower().startswith('start'):
            text = 'hola, quiero información'

    bot.send_chat_action(chat_id, 'typing')
    _responder(m, ask_deepseek(chat_id, text))

@bot.message_handler(content_types=['voice', 'audio'])
def on_audio(m):
    bot.reply_to(m, "😊 Por aquí no escucho audios todavía, pero escríbeme tu consulta y te atiendo de inmediato. 🚀")

@bot.message_handler(content_types=['document', 'video'])
def on_otros(m):
    # Puede ser un comprobante en PDF o video
    st = estado_cliente(m.chat.id)
    try:
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            telebot.types.InlineKeyboardButton("✅ PAGO CONFIRMADO", callback_data=f"okpay:{m.chat.id}"),
            telebot.types.InlineKeyboardButton("❌ Rechazar", callback_data=f"nopay:{m.chat.id}")
        )
        bot.send_message(ADMIN_CHAT,
            f"📎 *ARCHIVO DE {st['nombre']}* (chat `{m.chat.id}`)\n"
            f"Puede ser un comprobante de pago (PDF/video). Si es el pago, confirma aquí:",
            parse_mode='Markdown', reply_markup=markup)
        _responder(m, "📩 Recibido, ya lo pasé a validación. Te confirmo enseguida. 🚀")
    except Exception as e:
        log.error(f"archivo admin fallo: {e}")

def run_bot():
    log.info("Iniciando Bot A2K Systems v2.0 (Vendedor + Licencias)...")
    try:
        bot.delete_my_commands()
        log.info("Menú de comandos eliminado — bot 100% conversacional")
    except Exception as e:
        log.warning(f"no se pudo borrar el menú: {e}")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            log.error(f"polling cayo, reintento en 5s: {e}")
            time.sleep(5)

def iniciar_bot():
    global BOT_THREAD
    BOT_THREAD = threading.Thread(target=run_bot, daemon=True)
    BOT_THREAD.start()

if __name__ == '__main__':
    iniciar_bot()
    run_web()
