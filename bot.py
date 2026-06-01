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

SYSTEM_PROMPT = """Sen Avtomentor haydovchilik maktabi va online kurslarining yordamchi assistentisan.

HAYDOVCHILIK MAKTABI haqida:
- Brend: Avtomentor
- Joylashuv: Baliqchi tumani, Andijon viloyati
- Kategoriyalar: B va BC
- To'lovlar B toifa 5,5 milion , BC toifa 7,2 milion
- 3600+ dan ortiq o'quvchi bitirgan
- Pul qaytarish kafolati bor

ONLINE KURS haqida:
- Veb-sayt: avtomentorpro.uz
- 14 ta darsdan iborat to'liq kurs
- Yo'l harakati qoidalari imtihoniga tayyorgarlik
- Instagram: @avtomentor (128K+ obunachilar)

JAVOB BERISH QOIDALARI:
1. O'zbek tilida, do'stona va professional
2. Qisqa va aniq javob ber (3-5 jumladan ko'p emas)
3. Narx so'rasa: "Narx va batafsil ma'lumot uchun tez orada Asadbek aka o'zi bog'lanadi 🙏"
4. Online kurs so'rasa: avtomentorpro.uz ga yo'nalt
5. Birinchi xabarga salom bilan boshla
6. Oxirida: "Boshqa savolingiz bo'lsa yozing! 😊" de
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
