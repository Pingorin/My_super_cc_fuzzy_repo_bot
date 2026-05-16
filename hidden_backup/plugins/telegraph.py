from pyrogram import Client, filters

# ==============================================================================
# 🖼️ TELEGRAM NATIVE FILE_ID GENERATOR (100% NEVER FAILS)
# ==============================================================================

@Client.on_message(filters.command(["tg", "telegraph", "getid"]) & filters.private)
async def get_telegram_file_id(client, message):
    reply = message.reply_to_message
    
    # Check if replied to a photo
    if not reply or not reply.photo:
        return await message.reply_text("⚠️ **Sahi Tarika:** Apne QR Code (Photo) par reply karke `/getid` ya `/tg` type karein.")
    
    # Photo ka sabse high-quality version ka file_id nikalna
    file_id = reply.photo.file_id
    
    text = (
        f"✅ **QR Code File ID Generated!**\n\n"
        f"Telegraph aur dusre servers ko bhool jayiye. Telegram ka apna File ID sabse fast aur secure hai. Ye kabhi block/delete nahi hota!\n\n"
        f"📥 **Aapka File ID:**\n`{file_id}`\n\n"
        f"👉 **Use Kaise Karein?**\n"
        f"Is lambe se ID ko copy karein aur apne `info.py` mein `CUSTOM_QR_URL` ke aage paste kar dein.\n\n"
        f"**Example:**\n`CUSTOM_QR_URL = \"{file_id}\"`"
    )
    
    await message.reply_text(text)
