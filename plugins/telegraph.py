import os
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ==============================================================================
# 🖼️ TELEGRAPH IMAGE UPLOADER (400 ERROR 100% FIXED)
# ==============================================================================

@Client.on_message(filters.command(["tg", "telegraph"]) & filters.private)
async def telegraph_upload(client, message):
    reply = message.reply_to_message
    if not reply or not (reply.photo or reply.video or reply.animation or reply.document):
        return await message.reply_text("⚠️ **Sahi Tarika:** Kripya kisi Photo ya Video par reply karke `/tg` type karein.")

    # File size limit check (Telegraph allows max 5MB)
    file_size = getattr(reply.photo, "file_size", 0) or getattr(reply.video, "file_size", 0) or getattr(reply.animation, "file_size", 0) or getattr(reply.document, "file_size", 0)
    if file_size > 5242880:  # 5 MB in bytes
        return await message.reply_text("❌ **File Size Limit Exceeded!** Telegraph par sirf 5MB se choti files upload ho sakti hain.")

    msg = await message.reply_text("⏳ **Processing...** File download ho rahi hai...")
    
    # Extension aur Mime-Type check
    if reply.photo:
        ext = ".jpg"
        mime = "image/jpeg"
    elif reply.video or reply.animation:
        ext = ".mp4"
        mime = "video/mp4"
    elif reply.document:
        mime = reply.document.mime_type
        if mime and mime.startswith("image/"):
            ext = ".png" if "png" in mime else ".jpg"
        elif mime and mime.startswith("video/"):
            ext = ".mp4"
        else:
            return await msg.edit_text("❌ Kripya sirf Image ya Video file bhejein.")
    else:
        ext = ".jpg"
        mime = "image/jpeg"
        
    temp_file = f"tg_file_{message.from_user.id}{ext}"
    
    try:
        # File Download
        download_path = await client.download_media(message=reply, file_name=temp_file)
        
        await msg.edit_text("📤 **Uploading to Telegraph (graph.org)...**")
        
        async with aiohttp.ClientSession() as session:
            # 🛑 REAL FIX: File ko stream karne ke bajaye bytes read kar rahe hain
            with open(download_path, 'rb') as f:
                file_bytes = f.read() 
                
            form = aiohttp.FormData()
            # Ab hum directly bytes bhejenge taaki server 400 error na de
            form.add_field('file', file_bytes, filename=temp_file, content_type=mime)
            
            # Request to graph.org
            async with session.post("https://graph.org/upload", data=form) as response:
                if response.status == 200:
                    json_data = await response.json()
                    if type(json_data) is list and len(json_data) > 0 and 'src' in json_data[0]:
                        # Link Generation
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
                    else:
                        await msg.edit_text("❌ **Upload Failed!** Telegraph se valid data nahi mila.")
                else:
                    err_text = await response.text()
                    await msg.edit_text(f"❌ **Upload Failed:** Server ne {response.status} error diya.\n\n`{err_text}`")
                        
    except Exception as e:
        await msg.edit_text(f"❌ **Error Occurred:** `{e}`")
        
    finally:
        # Temporary file delete kar dena
        if 'download_path' in locals() and os.path.exists(download_path):
            os.remove(download_path)
