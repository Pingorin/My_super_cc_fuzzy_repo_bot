import os
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ==============================================================================
# 🖼️ TELEGRAPH IMAGE UPLOADER (graph.org)
# ==============================================================================

@Client.on_message(filters.command(["tg", "telegraph"]) & filters.private)
async def telegraph_upload(client, message):
    # Check karega ki kya command kisi photo/video ke reply me diya gaya hai
    reply = message.reply_to_message
    if not reply or not (reply.photo or reply.video or reply.animation or reply.document):
        return await message.reply_text("⚠️ **Sahi Tarika:** Kripya kisi Photo ya Video (under 5MB) par reply karke `/tg` ya `/telegraph` type karein.")

    # Check for valid document types
    if reply.document:
        if not (reply.document.mime_type.startswith("image/") or reply.document.mime_type.startswith("video/")):
            return await message.reply_text("❌ Kripya sirf Image ya Video file bhejein.")

    # File size limit check (Telegraph allows max 5MB)
    file_size = getattr(reply.photo, "file_size", 0) or getattr(reply.video, "file_size", 0) or getattr(reply.animation, "file_size", 0) or getattr(reply.document, "file_size", 0)
    if file_size > 5242880:  # 5 MB in bytes
        return await message.reply_text("❌ **File Size Limit Exceeded!** Telegraph par sirf 5MB se choti files upload ho sakti hain.")

    msg = await message.reply_text("⏳ **Processing...** File download ho rahi hai...")
    
    try:
        # 1. Download file to local storage
        download_path = await reply.download()
        
        await msg.edit_text("📤 **Uploading to Telegraph (graph.org)...**")
        
        # 2. Upload to graph.org API via aiohttp
        async with aiohttp.ClientSession() as session:
            with open(download_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=os.path.basename(download_path))
                
                async with session.post("https://graph.org/upload", data=form) as response:
                    if response.status == 200:
                        json_data = await response.json()
                        if type(json_data) is list and len(json_data) > 0 and 'src' in json_data[0]:
                            # 3. Generate Link
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
                            await msg.edit_text("❌ **Upload Failed!** Telegraph se koi valid response nahi mila.")
                    else:
                        await msg.edit_text(f"❌ **Error:** API returned status code {response.status}")
                        
    except Exception as e:
        await msg.edit_text(f"❌ **Error Occurred:** `{e}`")
        
    finally:
        # 4. Clean up (Delete the temporary downloaded file to save server space)
        if 'download_path' in locals() and os.path.exists(download_path):
            os.remove(download_path)

