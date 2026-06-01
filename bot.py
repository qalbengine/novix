import os
import openai
import asyncio
import traceback
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
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
- Ertalab / tushdan keyin / kechki online format
 
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
- Platform: avtomentorpro.uz (testlar, vazifalar)
- 100% imtihon topshirish kafolati (barcha vazifalar bajarilsa)
 
📚 Kurs jarayoni:
- Har kuni video dars
- avtomentorpro.uz da test ishlash
- Natijalar avtomatik tekshiriladi
- 3 kun sababsiz qatnashmaslik = kursdan chiqarilish
 
💳 To'lov: 9860100126865797 (Asadbek Axmatqulov)
To'lovdan so'ng chekni @avtomentor_admin ga yuboring
 
🔗 Foydali havolalar:
- Natijalar: https://t.me/Avtomentor_Info/3/1232
- YouTube: @ilhomjon_avtotest_rasmiy
- Telegram chat: @ilhomjon_avtotest_chat
 
━━━━━━━━━━━━━━━━━━━━━━
🤖 JAVOB BERISH QOIDALARI
━━━━━━━━━━━━━━━━━━━━━━
1. DOIM O'zbek tilida javob ber
2. Samimiy va do'stona bo'l — go'yo yaqin tanish kabi gapir
3. Qisqa javob ber — 3-5 jumla yetarli, kerak bo'lsa ko'proq
4. Savolga qarab tegishli ma'lumot ber:
   - Narx so'rasa → aniq narxni ayt
   - Ro'yxat so'rasa → @Aa_Asadbek ga yo'nalt
   - Online kurs so'rasa → avtomentorpro.uz va 600,000 so'm de
   - Imtihon so'rasa → offline 7 kunlik kurs haqida ayt
5. Suhbat oxirida yordam taklif qil: "Boshqa savolingiz bo'lsa yozing! 😊"
6. Bilmagan narsani o'ylab topma — "Asadbek aka bilan bog'laning: @Aa_Asadbek" de
7. Har doim iliq muloqot qil, sovuq robot kabi emas
"""
print(f"BOT_TOKEN mavjud: {bool(BOT_TOKEN)}")
print(f"OPENAI_API_KEY mavjud: {bool(OPENAI_API_KEY)}")

openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
user_histories = {}
app = Flask(__name__)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

application = Application.builder().token(BOT_TOKEN).build()

async def init_app():
    await application.initialize()
    await application.start()

loop.run_until_complete(init_app())


async def get_ai_reply(user_id, user_text):
    if user_id not in user_histories:
        user_histories[user_id] = []

    user_histories[user_id].append({"role": "user", "content": user_text})
    if len(user_histories[user_id]) > 10:
        user_histories[user_id] = user_histories[user_id][-10:]

    try:
        print(f"OpenAI ga so'rov: {user_text[:30]}")
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *user_histories[user_id]
            ],
            max_tokens=300,
            temperature=0.7
        )
        reply = response.choices[0].message.content
        print(f"OpenAI javob: {reply[:50]}")
        user_histories[user_id].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        print(f"OpenAI XATO: {str(e)}")
        print(traceback.format_exc())
        return "Hozir texnik muammo bor, tez orada Asadbek aka o'zi bog'lanadi! 🙏"


async def handle_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Oddiy xabar
    if update.message and update.message.text:
        print(f"Oddiy xabar: {update.message.text[:30]}")
        reply = await get_ai_reply(update.message.from_user.id, update.message.text)
        await update.message.reply_text(reply)

    # Business xabar
    elif update.business_message and update.business_message.text:
        print(f"Business xabar: {update.business_message.text[:30]}")
        reply = await get_ai_reply(
            update.business_message.from_user.id,
            update.business_message.text
        )
        await context.bot.send_message(
            chat_id=update.business_message.chat_id,
            text=reply,
            business_connection_id=update.business_message.business_connection_id
        )
    else:
        print(f"Boshqa update turi: {update}")


# Barcha updatelarni ushlash
application.add_handler(MessageHandler(filters.ALL, handle_update))


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print(f"Webhook keldi: {list(data.keys())}")
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
