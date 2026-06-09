import os
import openai
import asyncio
import traceback
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
ADMIN_ID = os.environ.get("ADMIN_ID", "")  # Admin Telegram ID si

SYSTEM_PROMPT = """Sen Avtomentor va Ilhomjon Avtotest loyihalarining aqlli yordamchi assistentisan. Ismingiz — Avto AI. 

Siz juda samimiy, muloyim va professional tarzda O'zbek tilida gaplashasiz. Javoblaringiz qisqa, aniq va odamdek tabiiy bo'lsin. Emojidan o'rinli foydalaning.

━━━━━━━━━━━━━━━━━━━━━━
🏫 HAYDOVCHILIK MAKTABI (Offline)
━━━━━━━━━━━━━━━━━━━━━━
Brend: Avtomentor / Ilhomjon Avtotest
📍 Joylashuv: Andijon viloyati, Baliqchi tumani
📞 Bog'lanish: @Aa_Asadbek | 932502719

🚗 B toifa:
- Narx: 5,500,000 so'm
- Davomiyligi: 2 oy 15 kun
- Haftada 6 dars (2 smena tanlovi)
- Nazariy + haftada 1 kun amaliy mashg'ulot

🚛 BC toifa:
- Narx: 7,200,000 so'm
- Davomiyligi: 5 oy 20 kun
- Haftada 6 dars (2 smena tanlovi)
- Nazariy + haftada 1 kun amaliy mashg'ulot

📅 Imtihonga tayyorlov (Offline intensiv):
- Davomiyligi: 7 kun
- Narx: 1,000,000 so'm
- 100% o'tish kafolati!
- Uzoqdan kelganlar uchun kvartira: 35,000 so'm/kun

━━━━━━━━━━━━━━━━━━━━━━
💻 ONLINE KURS (Ilhomjon Avtotest)
━━━━━━━━━━━━━━━━━━━━━━
- Narx: 600,000 so'm (1-dars bepul sinov, yoqmasa pul qaytariladi!)
- Davomiyligi: 14 kun
- Vaqt: Har kuni 20:00 — 22:00 (Dushanbadan Shanbagacha)
- Format: Google Meet orqali jonli darslar
- Platform: avtomentorpro.uz
- 100% imtihon topshirish kafolati

💳 To'lov: 9860100126865797 (Asadbek Axmatqulov)
To'lovdan so'ng chekni shu botga yuboring — admin tekshirib guruhga qo'shadi.

🔗 Foydali havolalar:
- Natijalar: https://t.me/Avtomentor_Info/3/1232
- YouTube: @ilhomjon_avtotest_rasmiy
- Telegram chat: @ilhomjon_avtotest_chat

━━━━━━━━━━━━━━━━━━━━━━
JAVOB BERISH QOIDALARI
━━━━━━━━━━━━━━━━━━━━━━
1. DOIM O'zbek tilida javob ber
2. Samimiy va do'stona bo'l
3. Qisqa javob ber — 3-5 jumla yetarli
4. Narx so'rasa → aniq narxni ayt
5. To'lov so'rasa → karta raqamini ayt va chekni shu botga yuborishni ayt
6. Bilmagan narsani o'ylab topma → "Asadbek aka bilan bog'laning: @Aa_Asadbek" de
7. Oxirida: "Boshqa savolingiz bo'lsa yozing! 😊" de
"""

# Foydalanuvchi holatlari
# STATE: "new" → "waiting_name" → "waiting_phone" → "active"
user_states = {}
user_info = {}
user_histories = {}

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

    # Guruh xabarlari — faqat mention da
    if hasattr(message, 'chat') and message.chat.type in ["group", "supergroup"]:
        bot_username = application.bot_data.get("username", "")
        if not (bot_username and bot_username.lower() in text.lower()):
            return
        clean_text = text.replace(bot_username, "").strip() or "Salom"
        reply = await get_ai_reply(user_id, clean_text)
        await process_message(context, chat_id, user_id, reply, business_connection_id)
        return

    state = user_states.get(user_id, "new")

    # YANGI FOYDALANUVCHI → Isim so'ra
    if state == "new":
        user_states[user_id] = "waiting_name"
        await process_message(
            context, chat_id, user_id,
            "Assalomu alaykum! 👋 Avtomentor yordamchi botiga xush kelibsiz!\n\n"
            "Davom etishdan oldin, iltimos ismingizni yozing:",
            business_connection_id
        )
        return

    # ISIM KUTILMOQDA
    elif state == "waiting_name":
        user_info[user_id] = {"name": text, "source": source}
        user_states[user_id] = "waiting_phone"
        await process_message(
            context, chat_id, user_id,
            f"Rahmat, {text}! 😊\n\nIltimos telefon raqamingizni yuboring:\n(Masalan: +998901234567)",
            business_connection_id
        )
        return

    # RAQAM KUTILMOQDA
    elif state == "waiting_phone":
        name = user_info.get(user_id, {}).get("name", "Noma'lum")
        user_info[user_id]["phone"] = text
        user_states[user_id] = "active"

        # Adminga xabar yuborish
        await notify_admin(context, user_id, name, text, source)

        await process_message(
            context, chat_id, user_id,
            f"✅ Rahmat, {name}!\n\n"
            f"Ma'lumotlaringiz saqlandi. Endi kurs yoki xizmatlar haqida savol bera olasiz!\n\n"
            f"Qanday yordam kerak? 😊",
            business_connection_id
        )
        return

    # FAOL FOYDALANUVCHI → AI javob
    elif state == "active":
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


application.add_handler(CommandHandler("start", start_command))
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
