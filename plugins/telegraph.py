import os
import requests
import mimetypes
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ==============================================================================
# 🖼️ TELEGRAPH IMAGE UPLOADER (FINAL 400 ERROR FIX - SHORT FILENAME TRICK)
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
        # 1. Download file
        download_path = await reply.download()
        
        # 2. Extract Type
        mime_type = mimetypes.guess_type(download_path)[0] or "image/jpeg"
        
        # 🛑 SABSE BADA FIX: Server ko lamba naam pasand nahi hai, isliye hum ek chota "Fake Name" banayenge
        if mime_type.startswith("video/"):
            fake_filename = "video.mp4"
        else:
            fake_filename = "image.jpg"
            
        await msg.edit_text("📤 **Uploading to graph.org...**")
        
        # 3. Synchronous upload function
        def upload_to_telegraph():
            with open(download_path, 'rb') as f:
                # Yahan humne server ko strictly chota naam (fake_filename) diya hai
                files = {'file': (fake_filename, f, mime_type)}
                
                # India me ban/block hone se bachne ke liye direct graph.org use kar rahe hain
                resp = requests.post("https://graph.org/upload", files=files)
                return resp.status_code, resp.text

        # 4. Async run_in_executor
        status_code, response_text = await client.loop.run_in_executor(None, upload_to_telegraph)
        
        if status_code == 200:
            import json
            try:
                json_data = json.loads(response_text)
                if type(json_data) is list and len(json_data) > 0 and 'src' in json_data[0]:
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
                elif type(json_data) is dict and "error" in json_data:
                    await msg.edit_text(f"❌ **API Error:** `{json_data['error']}`")
                else:
                    await msg.edit_text("❌ **Upload Failed!** Unknown Response format.")
            except Exception as json_err:
                await msg.edit_text("❌ **Upload Failed!** Server response format incorrect tha.")
        else:
            await msg.edit_text(f"❌ **Upload Failed: {status_code}**\n\n`{response_text}`")
            
    except Exception as e:
        await msg.edit_text(f"❌ **Error Occurred:** `{e}`")
        
    finally:
        # Storage clear
        if 'download_path' in locals() and download_path and os.path.exists(download_path):
            os.remove(download_path)
