import os
import requests
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ==============================================================================
# 🖼️ UNIVERSAL IMAGE UPLOADER (BYPASS TELEGRAPH BLOCKS)
# ==============================================================================

@Client.on_message(filters.command(["tg", "telegraph", "upload"]) & filters.private)
async def telegraph_upload(client, message):
    reply = message.reply_to_message
    if not reply or not (reply.photo or reply.video or reply.animation or reply.document):
        return await message.reply_text("⚠️ **Sahi Tarika:** Kripya kisi Photo ya Video par reply karke `/tg` type karein.")

    file_size = getattr(reply.photo, "file_size", 0) or getattr(reply.video, "file_size", 0) or getattr(reply.animation, "file_size", 0) or getattr(reply.document, "file_size", 0)
    if file_size > 5242880:  
        return await message.reply_text("❌ **File Size Limit Exceeded!** Sirf 5MB se choti files upload ho sakti hain.")

    msg = await message.reply_text("⏳ **Processing...** File download ho rahi hai...")
    
    try:
        # 1. File Download
        download_path = await reply.download()
        
        await msg.edit_text("📤 **Uploading to Premium Servers...**\n_(Bypassing Telegraph Block)_")
        
        # 2. Multi-Server Upload Logic
        def upload_multi_server():
            # 🔥 TRY 1: Envs.sh (Fastest & Unblocked)
            try:
                with open(download_path, 'rb') as f:
                    response = requests.post("https://envs.sh", files={"file": f}, timeout=15)
                    if response.status_code == 200 and response.text.startswith("http"):
                        return response.text.strip()
            except Exception:
                pass
            
            # 🔥 TRY 2: Catbox.moe (Reliable Fallback)
            try:
                with open(download_path, 'rb') as f:
                    response = requests.post("https://catbox.moe/user/api.php", data={"reqtype": "fileupload"}, files={"fileToUpload": f}, timeout=15)
                    if response.status_code == 200 and response.text.startswith("http"):
                        return response.text.strip()
            except Exception:
                pass

            return None

        # 3. Async run taaki bot atke nahi
        image_link = await client.loop.run_in_executor(None, upload_multi_server)
        
        if image_link:
            buttons = [
                [InlineKeyboardButton("🌐 Open Link", url=image_link)],
                [InlineKeyboardButton("🔗 Share Link", url=f"https://t.me/share/url?url={image_link}")]
            ]
            await msg.edit_text(
                f"✅ **Image Uploaded Successfully!**\n\n"
                f"📥 **Link:**\n`{image_link}`\n\n"
                f"_Aap is link ko copy karke apne info.py mein `CUSTOM_QR_URL` me daal sakte hain._",
                reply_markup=InlineKeyboardMarkup(buttons),
                disable_web_page_preview=False
            )
        else:
            await msg.edit_text("❌ **Upload Failed!**\n\nDono servers (Envs aur Catbox) par network error aaya. Kripya thodi der baad try karein.")
            
    except Exception as e:
        await msg.edit_text(f"❌ **Error Occurred:** `{e}`")
        
    finally:
        # Storage clear kar do
        if 'download_path' in locals() and download_path and os.path.exists(download_path):
            os.remove(download_path)

