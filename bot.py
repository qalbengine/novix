import os
import openai
import asyncio
import traceback
import time
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
ADMIN_ID = os.environ.get("ADMIN_ID", "")  # Admin Telegram ID si

SYSTEM_PROMPT = """Sen Avtomentor haydovchilik maktabi egasisisan — Asadbek. Mijozlar bilan yozishmoqdasiz.

MUHIM: Sen bot emassan. Hech qachon "Men bot" yoki "Men AI" dema. Oddiy odam kabi, qisqa va jonli yoz.

━━━━━━━━━━━━━━━━━━━━━━
KURSLAR MA'LUMOTI
━━━━━━━━━━━━━━━━━━━━━━
🚗 B toifa (offline):
- Narx: 5 500 000 so'm
- Muddat: 2 oy 15 kun, haftada 6 kun
- 2 smena: ertalab yoki kechki

🚛 BC toifa (offline):
- Narx: 7 200 000 so'm
- Muddat: 5 oy 20 kun, haftada 6 kun

📝 Imtihon tayyorlovi (intensiv):
- Narx: 1 000 000 so'm, 7 kun
- 100% o'tish kafolati
- Uzoqdan kelganlar: kvartira 35 000 so'm/kun

💻 Online kurs:
- Narx: 600 000 so'm
- 14 kun, har kuni kech 20:00-22:00
- Google Meet + avtomentorpro.uz platformasi
- 1-dars bepul sinov — yoqmasa pul qaytadi
- 100% imtihon kafolati

💳 To'lov: 9860100126865797 (Asadbek Axmatqulov)
Chekni @avtomentor_admin ga yuboring

━━━━━━━━━━━━━━━━━━━━━━
YOZISH USLUBI
━━━━━━━━━━━━━━━━━━━━━━
- Qisqa yoz: 1-3 jumla yetarli
- Oddiy so'zlashuv tili, rasmiy emas
- Savol bergan narsaga to'g'ri javob ber
- Kerak bo'lsa emoji ishlat, lekin ko'p emas
- Mijoz ismi/raqami yo'q bo'lsa, 2-3 xabardan keyin tabiiy so'ra:
  "Aytgancha, ismingiz nima edi? 😊" yoki "Raqamingizni qoldirsangiz, to'g'ridan bog'lanaman"
- Bilmagan narsani ixtiro qilma — "Asadbek aka bilan to'g'ridan gaplashing: @Aa_Asadbek"
- Hech qachon: "Boshqa savolingiz bo'lsa yozing" kabi standart bot iboralar ishlatma
"""

# Foydalanuvchi holatlari
# STATE: "new" → "waiting_name" → "waiting_phone" → "active"
user_states = {}
user_info = {}
user_histories = {}

# Bot holati
bot_paused = False          # /pause bilan to'liq o'chirish
paused_chats = {}           # {chat_id: timestamp} — siz javob bergan chatlar (30 daqiqa jim)
PAUSE_DURATION = 30 * 60    # 30 daqiqa (soniyalarda)

print(f"BOT_TOKEN mavjud: {bool(BOT_TOKEN)}")
print(f"OPENAI_API_KEY mavjud: {bool(OPENAI_API_KEY)}")
print(f"ADMIN_ID: {ADMIN_ID}")

openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
application = Application.builder().token(BOT_TOKEN).build()

async def init_app():
    await application.initialize()
    await application.start()
    bot_info = await application.bot.get_me()
    application.bot_data["username"] = f"@{bot_info.username}"
    print(f"Bot: @{bot_info.username}")

loop.run_until_complete(init_app())


async def get_ai_reply(user_id, user_text):
    if user_id not in user_histories:
        user_histories[user_id] = []

    user_histories[user_id].append({"role": "user", "content": user_text})
    if len(user_histories[user_id]) > 10:
        user_histories[user_id] = user_histories[user_id][-10:]

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *user_histories[user_id]
            ],
            max_tokens=400,
            temperature=0.8
        )
        reply = response.choices[0].message.content
        user_histories[user_id].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        print(f"OpenAI XATO: {str(e)}")
        return "Hozir texnik muammo bor, tez orada Asadbek aka o'zi bog'lanadi! 🙏"


async def notify_admin(context, user_id, name, phone, source="private"):
    """Adminga yangi mijoz haqida xabar yuborish"""
    if not ADMIN_ID:
        return
    try:
        msg = (
            f"🆕 Yangi mijoz!\n\n"
            f"👤 Ismi: {name}\n"
            f"📞 Raqami: {phone}\n"
            f"🔗 Telegram ID: {user_id}\n"
            f"📍 Kanal: {source}"
        )
        await context.bot.send_message(chat_id=int(ADMIN_ID), text=msg)
    except Exception as e:
        print(f"Admin xabari xato: {e}")


async def process_message(context, chat_id, user_id, text, business_connection_id=None):
    """Xabar yuborish — typing animatsiyasi bilan"""
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        delay = min(len(text) / 200, 3)
        await asyncio.sleep(max(delay, 1.2))
    except Exception:
        pass

    if business_connection_id:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            business_connection_id=business_connection_id
        )
    else:
        await context.bot.send_message(chat_id=chat_id, text=text)


async def handle_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message or update.business_message
    if not message or not message.text:
        return

    is_business = bool(update.business_message)
    business_connection_id = message.business_connection_id if is_business else None
    user_id = message.from_user.id
    chat_id = message.chat_id
    text = message.text.strip()
    source = "Business" if is_business else "Private"

    # Agar xabar sizdan (owner) kelsa — o'sha chatni 30 daqiqa pauza qil
    owner_id = int(ADMIN_ID) if ADMIN_ID else None
    if owner_id and user_id == owner_id and is_business:
        paused_chats[chat_id] = time.time()
        print(f"Owner javob berdi — chat {chat_id} pauza qilindi (30 daqiqa)")
        return

    # Bot to'liq pauzada bo'lsa — javob berma
    if bot_paused:
        print("Bot pauzada — javob berilmadi")
        return

    # Bu chat pauzada bo'lsa — tekshir
    if chat_id in paused_chats:
        elapsed = time.time() - paused_chats[chat_id]
        if elapsed < PAUSE_DURATION:
            print(f"Chat {chat_id} pauzada ({int((PAUSE_DURATION - elapsed) / 60)} daqiqa qoldi)")
            return
        else:
            del paused_chats[chat_id]  # Pauza tugadi

    # Guruh xabarlari — faqat mention da
    if hasattr(message, 'chat') and message.chat.type in ["group", "supergroup"]:
        bot_username = application.bot_data.get("username", "")
        if not (bot_username and bot_username.lower() in text.lower()):
            return
        clean_text = text.replace(bot_username, "").strip() or "Salom"
        reply = await get_ai_reply(user_id, clean_text)
        await process_message(context, chat_id, user_id, reply, business_connection_id)
        return

    # AI javob — to'g'ridan
    print(f"Xabar ({source}): {text[:30]}")
    reply = await get_ai_reply(user_id, text)
    await process_message(context, chat_id, user_id, reply, business_connection_id)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    # Holatni reset qilib qaytadan boshlash
    user_states[user_id] = "new"
    user_info.pop(user_id, None)
    user_histories.pop(user_id, None)
    await handle_update(update, context)


async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_paused
    owner_id = int(ADMIN_ID) if ADMIN_ID else None
    if update.message.from_user.id == owner_id:
        bot_paused = True
        await update.message.reply_text("⏸ Bot pauza qilindi. Barcha xabarlarga o'zingiz javob berasiz.")
    else:
        await update.message.reply_text("Bu buyruq faqat admin uchun.")


async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_paused
    owner_id = int(ADMIN_ID) if ADMIN_ID else None
    if update.message.from_user.id == owner_id:
        bot_paused = False
        paused_chats.clear()
        await update.message.reply_text("▶️ Bot yoqildi. Endi barcha xabarlarga javob beradi.")
    else:
        await update.message.reply_text("Bu buyruq faqat admin uchun.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    owner_id = int(ADMIN_ID) if ADMIN_ID else None
    if update.message.from_user.id != owner_id:
        return
    status = "⏸ Pauza" if bot_paused else "▶️ Faol"
    paused_count = len(paused_chats)
    await update.message.reply_text(
        f"🤖 Bot holati: {status}
"
        f"💬 Pauza qilingan chatlar: {paused_count} ta

"
        f"Buyruqlar:
"
        f"/pause — Botni to'xtatish
"
        f"/resume — Botni yoqish"
    )


application.add_handler(CommandHandler("start", start_command))
application.add_handler(CommandHandler("pause", pause_command))
application.add_handler(CommandHandler("resume", resume_command))
application.add_handler(CommandHandler("status", status_command))
application.add_handler(MessageHandler(filters.ALL, handle_update))


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    update = Update.de_json(data, application.bot)
    loop.run_until_complete(application.process_update(update))
    return "OK", 200


@app.route("/")
def index():
    return "Avtomentor Bot ishlamoqda! ✅", 200


@app.route("/set_webhook")
def set_webhook():
    url = f"{WEBHOOK_URL}/webhook"
    loop.run_until_complete(application.bot.set_webhook(url=url))
    return f"Webhook o'rnatildi: {url}", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
