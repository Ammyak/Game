import asyncio
import logging
import os
import httpx
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, LabeledPrice,
    PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton
)

# ─── Конфигурация ─────────────────────────────────────────────────────────────
BOT_TOKEN    = os.environ.get("BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
PRODUCT_URL  = os.environ.get("PRODUCT_URL", "https://your-link.com")
STARS_PRICE  = 50
PORT         = int(os.environ.get("PORT", 8080))

# ─── Триггеры по темам ────────────────────────────────────────────────────────
TRIGGERS: dict[str, list[str]] = {
    "fps": [
        "fps", "фпс", "фреймы", "frames", "frame rate", "частота кадров",
    ],
    "lag": [
        "lag", "лаг", "лаги", "фриз", "freeze", "stuttering", "stutters",
        "latency", "задержка", "пинг", "ping",
    ],
    "boost": [
        "boost", "буст", "разогнать", "overclock", "ускорить", "speed up",
        "tweak", "твик", "оптимизация", "optimization", "optimize",
    ],
    "system": [
        "windows", "виндовс", "реестр", "registry", "планировщик", "scheduler",
        "bios", "биос", "драйвер", "driver", "cpu", "gpu", "ram", "озу",
    ],
    "help": [
        "help", "помощь", "помоги", "подскажи", "как", "what", "why",
        "настройка", "setting", "config", "конфиг",
    ],
}

# Плоский список для быстрой проверки
ALL_TRIGGERS = [w for words in TRIGGERS.values() for w in words]

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()

# ─── Groq / Llama ─────────────────────────────────────────────────────────────
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are TurboCat — an AI assistant for ANONYM SYSTEMS v3.0. "
    "You help gamers squeeze maximum FPS and eliminate lag on Windows PCs. "
    "Be cool, use gamer slang, keep answers concise (≤ 250 words). "
    "Always answer in the same language the user writes in (RU or EN)."
)

async def ask_ai(user_text: str) -> str:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama3-8b-8192",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_text},
        ],
        "temperature": 0.65,
        "max_tokens": 512,
    }

    async with httpx.AsyncClient(timeout=25.0) as client:
        try:
            r = await client.post(GROQ_URL, headers=headers, json=payload)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            log.error("Groq HTTP error %s: %s", e.response.status_code, e.response.text)
            return "🐈 Groq вернул ошибку. Попробуй чуть позже!"
        except httpx.RequestError as e:
            log.error("Groq request error: %s", e)
            return "🐈 Не могу достучаться до AI. Проверь соединение!"
        except Exception as e:
            log.error("Unexpected AI error: %s", e)
            return "🐈 Мои кошачьи мозги перегрелись. Попробуй позже!"

# ─── Клавиатура ───────────────────────────────────────────────────────────────
def buy_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=f"🚀 Купить ANONYM SYSTEMS ({STARS_PRICE} ⭐)",
            callback_data="buy"
        )
    ]])

# ─── Определение активной темы-триггера ───────────────────────────────────────
def detect_topic(text: str) -> str | None:
    """Возвращает название темы (ключ TRIGGERS) или None."""
    low = text.lower()
    for topic, words in TRIGGERS.items():
        if any(w in low for w in words):
            return topic
    return None

# ─── Хендлер сообщений ────────────────────────────────────────────────────────
@dp.message(F.text)
async def on_message(message: Message):
    text = message.text.strip()
    low  = text.lower()

    # /start
    if low == "/start":
        await message.answer(
            "🐈 <b>ANONYM SYSTEMS v3.0</b>\n\n"
            "Максимальный FPS и ноль лагов. Спрашивай — я отвечу!\n"
            "Пиши про <i>fps / лаги / boost / windows / помощь</i> — и AI включится.\n\n"
            f"Цена пакета: <b>{STARS_PRICE} ⭐ Stars</b>",
            parse_mode="HTML",
            reply_markup=buy_kb(),
        )
        return

    # Приветствие
    if any(w in low for w in ("привет", "hello", "хай", "ку", "hi", "hey")):
        await message.answer("Мяу! 🐈 Я TurboCat. Готов разнести твои лаги в пух и прах! 🚀")
        return

    # Вопросы о безопасности
    if any(w in low for w in ("безопасно", "safe", "вирус", "virus", "рат", "rat", "malware")):
        await message.answer(
            "🛡️ <b>Безопасность:</b>\n"
            "• Открытый исходный код (Open Source)\n"
            "• Мы не собираем данные пользователей\n"
            "• Только <code>.bat</code> и <code>.reg</code> — никакого стороннего кода",
            parse_mode="HTML",
        )
        return

    # Вопросы о покупке
    if any(w in low for w in ("купить", "buy", "цена", "стоимость", "stars", "price", "сколько")):
        await message.answer(
            f"💰 Пакет ANONYM SYSTEMS — <b>{STARS_PRICE} ⭐ Stars</b>.\n"
            "Нажми кнопку ниже!",
            parse_mode="HTML",
            reply_markup=buy_kb(),
        )
        return

    # Тема-триггер → AI
    topic = detect_topic(text)
    if topic:
        topic_labels = {
            "fps":    "📈 FPS",
            "lag":    "⚡ Лаги / Задержки",
            "boost":  "🚀 Буст",
            "system": "🖥️ Система",
            "help":   "🤖 Помощь",
        }
        label = topic_labels.get(topic, "🤖 AI")
        thinking = await message.answer(f"{label} — <i>TurboCat думает...</i>", parse_mode="HTML")
        answer = await ask_ai(text)
        await thinking.delete()
        await message.answer(f"🤖 <b>{label}:</b>\n\n{answer}", parse_mode="HTML")
        return

    # Ничего не подошло
    await message.answer(
        "🐾 Хм, не понял тему. Напиши что-нибудь про:\n"
        "<i>fps / лаги / boost / windows / помощь</i>",
        parse_mode="HTML",
    )

# ─── Оплата ───────────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "buy")
async def on_buy(call: CallbackQuery):
    await bot.send_invoice(
        chat_id=call.from_user.id,
        title="ANONYM SYSTEMS v3.0",
        description="Полный пакет оптимизации ПК для максимального FPS",
        payload="anonym_systems_v3",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="XTR", amount=STARS_PRICE)],
    )
    await call.answer()

@dp.pre_checkout_query()
async def on_pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def on_payment(message: Message):
    await message.answer(
        f"✅ <b>Оплата прошла!</b>\n\n"
        f"Вот твоя ссылка на пакет:\n{PRODUCT_URL}",
        parse_mode="HTML",
    )

# ─── Веб-сервер (healthcheck) ─────────────────────────────────────────────────
async def healthcheck(request):
    return web.Response(text="ok")

# ─── Точка входа ─────────────────────────────────────────────────────────────
async def main():
    app = web.Application()
    app.router.add_get("/", healthcheck)

    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    log.info("Web server started on port %d", PORT)

    await bot.delete_webhook(drop_pending_updates=True)
    log.info("Bot started polling")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())