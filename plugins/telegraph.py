import os
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ==============================================================================
# 🖼️ ULTIMATE IMAGE UPLOADER (IMGBB API - 100% UNBLOCKED)
# ==============================================================================

# ImgBB Public API Key (Stable & Free)
IMGBB_API_KEY = "318b7eb25e791e2b694b83b38c233fde"

@Client.on_message(filters.command(["tg", "telegraph", "upload"]) & filters.private)
async def telegraph_upload(client, message):
    reply = message.reply_to_message
    if not reply or not (reply.photo or reply.video or reply.animation or reply.document):
        return await message.reply_text("⚠️ **Sahi Tarika:** Kripya kisi Photo par reply karke `/tg` type karein.")

    file_size = getattr(reply.photo, "file_size", 0) or getattr(reply.video, "file_size", 0) or getattr(reply.animation, "file_size", 0) or getattr(reply.document, "file_size", 0)
    if file_size > 5242880:  
        return await message.reply_text("❌ **File Size Limit Exceeded!** Sirf 5MB se choti files upload ho sakti hain.")

    msg = await message.reply_text("⏳ **Processing...** File download ho rahi hai...")
    
    try:
        download_path = await reply.download()
        await msg.edit_text("📤 **Uploading to Premium ImgBB Server...**\n_(100% Secure & Unblocked)_")
        
        async with aiohttp.ClientSession() as session:
            with open(download_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('image', f)
                
                # Official ImgBB API Call
                async with session.post(f"https://api.imgbb.com/1/upload?key={IMGBB_API_KEY}", data=form) as response:
                    if response.status == 200:
                        json_data = await response.json()
                        image_link = json_data['data']['url']
                        
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
                        error_text = await response.text()
                        await msg.edit_text(f"❌ **Upload Failed!**\n\nServer Response: `{error_text}`")
                        
    except Exception as e:
        await msg.edit_text(f"❌ **Error Occurred:** `{e}`")
        
    finally:
        # Memory bachane ke liye file ko delete karna
        if 'download_path' in locals() and download_path and os.path.exists(download_path):
            os.remove(download_path)

