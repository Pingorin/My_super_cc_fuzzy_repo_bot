import os
import requests
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ==============================================================================
# 🖼️ TELEGRAPH IMAGE UPLOADER (100% FIXED WITH REQUESTS)
# ==============================================================================

@Client.on_message(filters.command(["tg", "telegraph"]) & filters.private)
async def telegraph_upload(client, message):
    reply = message.reply_to_message
    if not reply or not (reply.photo or reply.video or reply.animation or reply.document):
        return await message.reply_text("⚠️ **Sahi Tarika:** Kripya kisi Photo ya Video par reply karke `/tg` type karein.")

    file_size = getattr(reply.photo, "file_size", 0) or getattr(reply.video, "file_size", 0) or getattr(reply.animation, "file_size", 0) or getattr(reply.document, "file_size", 0)
    if file_size > 5242880:  
        return await message.reply_text("❌ **File Size Limit Exceeded!** Telegraph par sirf 5MB se choti files upload ho sakti hain.")

    msg = await message.reply_text("⏳ **Processing...** File download ho rahi hai...")
    
    try:
        # File Download
        download_path = await reply.download()
        
        await msg.edit_text("📤 **Uploading to Telegraph...**")
        
        # 🛑 BRAHMASTRA: aiohttp ki jagah 'requests' use kar rahe hain
        def upload_to_telegraph():
            with open(download_path, 'rb') as f:
                # requests file headers natively manage kar leta hai
                return requests.post("https://telegra.ph/upload", files={'file': f})

        # Async bot ko block hone se bachane ke liye executor me run kiya
        response = await client.loop.run_in_executor(None, upload_to_telegraph)
        
        if response.status_code == 200:
            json_data = response.json()
            
            if type(json_data) is list and len(json_data) > 0 and 'src' in json_data[0]:
                # 🌐 Link Generation (Telegra.ph ki jagah graph.org de rahe hain taaki India me ban na ho)
                telegraph_link = "https://graph.org" + json_data[0]['src']
                
                buttons = [
                    [InlineKeyboardButton("🌐 Open Link", url=telegraph_link)],
                    [InlineKeyboardButton("🔗 Share Link", url=f"https://t.me/share/url?url={telegraph_link}")]
                ]
                await msg.edit_text(
                    f"✅ **Telegraph Link Generated Successfully!**\n\n"
                    f"📥 **Link:**\n`{telegraph_link}`\n\n"
                    f"_Aap is link ko copy karke apne info.py mein `CUSTOM_QR_URL` me daal sakte hain._",
                    reply_markup=InlineKeyboardMarkup(buttons),
                    disable_web_page_preview=False
                )
            elif "error" in json_data:
                await msg.edit_text(f"❌ **Error:** {json_data['error']}")
            else:
                await msg.edit_text("❌ **Upload Failed!** Unknown Response.")
        else:
            await msg.edit_text(f"❌ **Upload Failed:** Server ne {response.status_code} error diya.\n\n`{response.text}`")
            
    except Exception as e:
        await msg.edit_text(f"❌ **Error Occurred:** `{e}`")
        
    finally:
        # Storage clear
        if 'download_path' in locals() and os.path.exists(download_path):
            os.remove(download_path)
