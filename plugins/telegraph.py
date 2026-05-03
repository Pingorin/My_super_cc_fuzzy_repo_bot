import os
import requests
import mimetypes
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ==============================================================================
# 🖼️ TELEGRAPH IMAGE UPLOADER (WITH ADVANCED DEBUGGING)
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
        
        # 2. File ki details nikalna (Debugging & Fixing ke liye)
        file_name = os.path.basename(download_path)
        mime_type = mimetypes.guess_type(download_path)[0]
        
        # Agar mimetype detect na ho ya file me extension na ho
        if not mime_type:
            mime_type = "image/jpeg"
        if "." not in file_name:
            file_name += ".jpg"
            
        file_bytes_size = os.path.getsize(download_path)
        
        await msg.edit_text(
            f"📤 **Uploading to Telegraph...**\n\n"
            f"🔍 **Debug Info:**\n"
            f"File: `{file_name}`\n"
            f"Type: `{mime_type}`\n"
            f"Size: `{file_bytes_size} bytes`\n\n"
            f"Server se response ka wait kar rahe hain..."
        )
        
        # 3. Synchronous upload function (Proper multipart form formatting)
        def upload_to_telegraph():
            with open(download_path, 'rb') as f:
                # 🛑 SABSE BADA FIX: Explicitly (filename, file_object, content_type) define karna zaroori hai!
                files = {'file': (file_name, f, mime_type)}
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
                }
                # Telegra.ph official API
                resp = requests.post("https://telegra.ph/upload", files=files, headers=headers)
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
                    await msg.edit_text(f"❌ **API Error:** `{json_data['error']}`\n\n🔍 **Raw Response:**\n`{response_text}`")
                else:
                    await msg.edit_text(f"❌ **Upload Failed!** Unknown Response format.\n\n🔍 **Raw Response:**\n`{response_text}`")
            except Exception as json_err:
                await msg.edit_text(f"❌ **JSON Parsing Error:** `{json_err}`\n\n🔍 **Raw Text from Server:**\n`{response_text}`")
        else:
            await msg.edit_text(
                f"❌ **Upload Failed: 400 Bad Request**\n\n"
                f"🚨 **Server ka Jawab:**\n`{response_text}`\n\n"
                f"🔍 **Hamne Kya Bheja Tha:**\n"
                f"Name: `{file_name}`\n"
                f"Type: `{mime_type}`\n"
                f"Size: `{file_bytes_size} bytes`"
            )
            
    except Exception as e:
        import traceback
        err_trace = traceback.format_exc()
        await msg.edit_text(f"❌ **Code Crash Occurred:**\n\n`{e}`\n\n🔍 **Traceback:**\n`{err_trace[-500:]}`")
        
    finally:
        # Storage clear
        if 'download_path' in locals() and download_path and os.path.exists(download_path):
            os.remove(download_path)

