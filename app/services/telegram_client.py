"""
Kairos AI — Telegram Client
Wrapper for Telegram Bot API to send driver alerts.
"""
import os
import asyncio
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

_bot = None


def get_bot() -> Bot:
    """Get the Telegram Bot instance (singleton)."""
    global _bot
    if _bot is not None:
        return _bot

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in environment variables.")

    _bot = Bot(token=token)
    return _bot


async def send_driver_message(chat_id: str, message: str) -> bool:
    """
    Send a message to a driver via Telegram.
    
    Args:
        chat_id: Driver's Telegram chat ID
        message: Message text (supports Markdown)
        
    Returns: True if sent successfully
    """
    try:
        bot = get_bot()
        await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode="Markdown"
        )
        return True
    except Exception as e:
        print(f"[Telegram] Failed to send message to {chat_id}: {e}")
        return False


async def send_dispatch_alert(
    chat_id: str,
    patient_name: str,
    blood_group: str,
    conditions: str,
    pickup_lat: float,
    pickup_lng: float,
    prep_instructions: list
):
    """
    Send a formatted dispatch alert to the ambulance driver.
    """
    maps_link = f"https://maps.google.com/?q={pickup_lat},{pickup_lng}"
    prep_text = "\n".join([f"  • {p}" for p in prep_instructions]) if prep_instructions else "  • Standard protocol"

    message = (
        f"🚨 *EMERGENCY DISPATCH* 🚨\n\n"
        f"*Patient:* {patient_name or 'Unidentified'}\n"
        f"*Blood Group:* {blood_group or 'Unknown'}\n"
        f"*Conditions:* {conditions or 'None reported'}\n\n"
        f"📍 *Pickup Location:*\n{maps_link}\n\n"
        f"🏥 *Prep Instructions:*\n{prep_text}\n\n"
        f"⚡ Respond ASAP. Drive safe."
    )

    await send_driver_message(chat_id, message)


async def send_hospital_nav(
    chat_id: str,
    hospital_name: str,
    hospital_lat: float,
    hospital_lng: float,
    reason: str
):
    """
    Send hospital navigation link to the driver after routing.
    """
    maps_link = f"https://maps.google.com/?q={hospital_lat},{hospital_lng}"

    message = (
        f"🏥 *HOSPITAL CONFIRMED* 🏥\n\n"
        f"*Hospital:* {hospital_name}\n"
        f"*Navigate:* {maps_link}\n\n"
        f"*Reason:* {reason}\n\n"
        f"🚑 Proceed immediately."
    )

    await send_driver_message(chat_id, message)
