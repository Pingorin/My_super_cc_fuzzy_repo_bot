import os
import aiohttp
import mimetypes
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ==============================================================================
# 🖼️ TELEGRAPH IMAGE UPLOADER (SUPER STABLE)
# ==============================================================================

@Client.on_message(filters.command(["tg", "telegraph"]) & filters.private)
async def telegraph_upload(client, message):
    # Check karega ki kya command kisi photo/video ke reply me diya gaya hai
    reply = message.reply_to_message
    if not reply or not (reply.photo or reply.video or reply.animation or reply.document):
        return await message.reply_text("⚠️ **Sahi Tarika:** Kripya kisi Photo ya Video par reply karke `/tg` type karein.")

    # File size limit check (Telegraph allows max 5MB)
    file_size = getattr(reply.photo, "file_size", 0) or getattr(reply.video, "file_size", 0) or getattr(reply.animation, "file_size", 0) or getattr(reply.document, "file_size", 0)
    if file_size > 5242880:  # 5 MB in bytes
        return await message.reply_text("❌ **File Size Limit Exceeded!** Telegraph par sirf 5MB se choti files upload ho sakti hain.")

    msg = await message.reply_text("⏳ **Processing...** File download ho rahi hai...")
    
    try:
        # 1. Download file to local storage
        download_path = await reply.download()
        
        await msg.edit_text("📤 **Uploading to Telegraph...**")
        
        # 2. File ka extension detect karna (Very Important for Telegraph API)
        content_type = mimetypes.guess_type(download_path)[0] or 'image/jpeg'
        
        # 3. Fake User-Agent set karna taaki server block na kare
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
        }
        
        # 4. Upload to API via aiohttp
        async with aiohttp.ClientSession(headers=headers) as session:
            with open(download_path, 'rb') as f:
                form = aiohttp.FormData()
                # File proper format aur content type ke sath bhej rahe hain
                form.add_field('file', f, filename=os.path.basename(download_path), content_type=content_type)
                
                # telegra.ph API use kar rahe hain (It is the official and more stable endpoint)
                async with session.post("https://telegra.ph/upload", data=form) as response:
                    
                    if response.status == 200:
                        json_data = await response.json()
                        if type(json_data) is list and len(json_data) > 0 and 'src' in json_data[0]:
                            # Generate Link
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
                        await msg.edit_text(f"❌ **Upload Failed:** Server ne {response.status} error diya.")
                        
    except Exception as e:
        await msg.edit_text(f"❌ **Error Occurred:** `{e}`")
        
    finally:
        # 5. Clean up local storage
        if 'download_path' in locals() and os.path.exists(download_path):
            os.remove(download_path)
