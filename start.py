#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A2K Digital Studio — Bot de Ventas de SISTEMAS (@zync_shop_bot)
Vende: POS/inventarios, landing pages, asistentes virtuales, bots de voz,
automatizaciones n8n. Cerebro DeepSeek + Flask keep-alive + /mensajes (voz).
v1.0
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
4. CONVENCE: manejo de objeciones — "está caro" → valor (paga una vez, es suyo, soporte incluido, multiplica ventas); "lo pienso" → cupos de implementación limitados; "no soy tecnológico" → lo instalamos y enseñamos TODO.
5. CIERRA asumiendo: "¿con cuál arrancamos: Bodega o el de tu rubro?" o "¿cómo prefieres pagar: Zelle, Binance o Bs a tasa USDT?". Todo mensaje termina en pregunta que avance la venta.

CATÁLOGO OFICIAL — SISTEMAS ($25 USD c/u, licencia de por vida + soporte):
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
- 📊 A2K Financial Dashboard — finanzas personales/empresa
- 🤖 Recepcionista AI — atiende clientes 24/7 por WhatsApp/web

SERVICIOS A MEDIDA (cotización según proyecto):
- 🌐 Landing pages profesionales
- 🤖 Asistentes virtuales para cualquier empresa
- 🎙️ Bots de voz
- ⚙️ Automatizaciones n8n (flujos de ventas, respaldos, publicaciones)

REGLAS DE ORO:
- Precios SOLO del catálogo. Sistemas: $25 USD c/u. Servicios a medida: cotizar, nunca inventar precio.
- Soporte e instalación incluidos. Licencia de por vida.
- Los sistemas son apps/programs que el cliente usa en su PC o celular.
- Si pide algo fuera de catálogo o hablar con humano: asesor WhatsApp wa.me/584164117331
- Nunca mientas sobre capacidades ni tiempos.

MÉTODOS DE PAGO: Zelle, bolívares a tasa USDT (P2P), Binance USDT. Pide comprobante siempre."""

conversations = {}
bot = telebot.TeleBot(TELEGRAM_TOKEN)

def _responder(m, texto):
    """Envía con Markdown y, si Telegram rechaza el formato, reintenta en plano."""
    try:
        bot.reply_to(m, texto, parse_mode='Markdown')
    except Exception:
        try:
            bot.reply_to(m, texto)
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

@bot.message_handler(commands=['start'])
def welcome(m):
    nombre = f" {m.from_user.first_name}" if m.from_user and m.from_user.first_name else ""
    _responder(m,
        f"🚀 *¡Bienvenido a A2K Digital Studio{nombre}!*\n\n"
        "Creamos los *sistemas y asistentes digitales* que hacen crecer negocios: "
        "puntos de venta, inventarios, páginas web, asistentes virtuales y automatizaciones. 🤖\n\n"
        "Tenemos un sistema listo para *cada rubro* — y si necesitas algo a tu medida, lo construimos.\n\n"
        "¿Qué tipo de negocio tienes o qué quieres lograr? Escríbeme con confianza: "
        "aquí no hay comandos ni botones raros — te leo y te respondo como una asesora real. 😎")

@bot.message_handler(content_types=['text'])
def on_text(m):
    chat_id, text = m.chat.id, m.text.strip()
    if not text.startswith('/'):
        nid = int(time.time() * 1000)
        msg_counter[0] = max(nid, msg_counter[0] + 1)
        clientes_mensajes.append({"id": msg_counter[0],
            "usuario": (m.from_user.first_name or "Cliente")[:30],
            "texto": text[:500], "hora": datetime.now().strftime('%H:%M:%S')})
        del clientes_mensajes[:-100]
    else:
        # Sin menú de comandos: lo que escriba con "/" se convierte en pregunta normal
        text = text.lstrip('/').replace('_', ' ')
        if text.lower().startswith('start'):
            text = 'hola, quiero información'
    bot.send_chat_action(chat_id, 'typing')
    _responder(m, ask_deepseek(chat_id, text))

@bot.message_handler(content_types=['voice', 'audio'])
def on_audio(m):
    bot.reply_to(m, "😊 Por aquí no escucho audios todavía, pero escríbeme tu consulta y te atiendo de inmediato. 🚀")

def run_bot():
    log.info("Iniciando Bot A2K Systems (Vendedor)...")
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
