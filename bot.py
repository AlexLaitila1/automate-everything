"""
OpenClaw Telegram bot.

Required env vars (add to .env):
    TELEGRAM_BOT_TOKEN  — from @BotFather
    ANTHROPIC_API_KEY   — from console.anthropic.com

Run:
    .venv/bin/python bot.py
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Any

import anthropic
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

from skills import TOOLS, execute_tool
from skills.blueprint.orchestrator import analyze_blueprint  # called directly for photos

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = (
    "You are OpenClaw, a helpful Telegram assistant. "
    "Use your tools whenever they would improve your answer. "
    "When a user sends a blueprint image, use the analyze_blueprint tool."
)

_TEXT_MODEL = "claude-haiku-4-5-20251001"


async def run_agent(
    user_message: str | list[dict[str, Any]],
    model: str = _TEXT_MODEL,
) -> str:
    """Send a message to Claude, handle tool calls, and return the final reply."""
    messages: list[dict] = [{"role": "user", "content": user_message}]

    while True:
        response = claude.messages.create(
            model=model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in reversed(response.content):
                if hasattr(block, "text"):
                    return block.text
            return "(no reply)"

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                log.info("Tool call: %s %s", block.name, {
                    k: v[:40] + "..." if isinstance(v, str) and len(v) > 40 else v
                    for k, v in block.input.items()
                })
                result = await execute_tool(block.name, block.input)
                log.info("Tool result length: %d chars", len(result))
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
            messages.append({"role": "user", "content": tool_results})
            continue

        return f"(stopped: {response.stop_reason})"


async def handle_message(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = update.message.text or ""
    log.info("User text: %s", user_text)
    reply = await run_agent(user_text)
    await update.message.reply_text(reply)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Analyzing blueprint, please wait...")

    try:
        photo = update.message.photo[-1]  # largest available size
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()
    except Exception as exc:
        log.error("Failed to download photo: %s", exc)
        await update.message.reply_text("Could not download the image. Please try again.")
        return

    image_base64 = base64.b64encode(image_bytes).decode()
    caption = update.message.caption or ""
    material = _detect_material(caption)

    reply = await analyze_blueprint({
        "image_base64": image_base64,
        "media_type": "image/jpeg",
        "material": material,
    })
    await update.message.reply_text(reply)


def _detect_material(caption: str) -> str:
    """Pick a cladding material from the caption text, defaulting to fiber_cement."""
    caption_lower = caption.lower()
    material_map = {
        "vinyl": "vinyl_siding",
        "brick": "brick",
        "fiber": "fiber_cement",
        "cement": "fiber_cement",
        "wood": "wood",
        "stucco": "stucco",
    }
    for keyword, key in material_map.items():
        if keyword in caption_lower:
            return key
    return "fiber_cement"


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    log.info("OpenClaw is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
