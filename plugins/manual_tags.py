import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from database.ia_filterdb import Media
from info import ADMINS

logger = logging.getLogger(__name__)

@Client.on_message(filters.command("addtag") & filters.user(ADMINS))
async def add_manual_tag(client, message: Message):
    # Check karega ki admin ne kisi file par reply kiya hai ya nahi
    if not message.reply_to_message:
        return await message.reply("⚠️ **Kripya kisi video ya document par reply karke command dein.**\n\n**Example:** `/addtag Tiger 3, Salman Khan, Hindi Dubbed`")

    media = message.reply_to_message.document or message.reply_to_message.video
    if not media:
        return await message.reply("⚠️ **Jiss message par aapne reply kiya hai, usme koi video ya file nahi hai!**")

    # Command aur tags ko alag karega
    tags_data = message.text.split(maxsplit=1)
    if len(tags_data) < 2:
        return await message.reply("⚠️ **Aapne koi tag nahi likha!**\n\n**Example:** `/addtag marvel, hindi, 2024`")

    new_tags = tags_data[1].strip()

    status_msg = await message.reply("⏳ **Tags add kar raha hoon...**")

    # Database mein file ko uske unique ID se dhundhega
    file_data = await Media.data_col.find_one({"file_unique_id": media.file_unique_id})

    if not file_data:
        return await status_msg.edit_text("❌ **Ye file abhi database mein save nahi hai!**\nPehle is file ko channel me daal kar index hone dein.")

    link_id = file_data['_id']

    # Search database mein file ka caption update karega (hidden tags add karega)
    search_data = await Media.search_col.find_one({"link_id": link_id})
    if not search_data:
        return await status_msg.edit_text("❌ **File ka search data nahi mila!**")

    old_caption = search_data.get("caption") or ""
    
    # Naye tags ko purane caption ke saath jod dega (Taki search me aa jaye)
    updated_caption = f"{old_caption} {new_tags}"

    # Database update command
    await Media.search_col.update_one(
        {"link_id": link_id},
        {"$set": {"caption": updated_caption}}
    )

    file_name = search_data.get('file_name', 'Unknown File')
    
    await status_msg.edit_text(
        f"✅ **Tags Successfully Added!**\n\n"
        f"📂 **File:** `{file_name}`\n"
        f"🏷️ **Added Tags:** `{new_tags}`\n\n"
        f"*(Ab koi bhi user in tags ko search karke ye file le sakta hai)*"
    )

@Client.on_message(filters.command("cleartags") & filters.user(ADMINS))
async def clear_manual_tag(client, message: Message):
    # Agar galti se galat tag lag jaye, toh usko remove karne ke liye
    if not message.reply_to_message:
        return await message.reply("⚠️ **Kripya us video/document par reply karein jiske tags delete karne hain.**")

    media = message.reply_to_message.document or message.reply_to_message.video
    if not media: return await message.reply("⚠️ **Ye koi video/document nahi hai!**")

    file_data = await Media.data_col.find_one({"file_unique_id": media.file_unique_id})
    if not file_data: return await message.reply("❌ **Ye file database mein save nahi hai!**")

    link_id = file_data['_id']
    
    # Caption ko completely clear kar dega (Sirf original file name bachega search ke liye)
    await Media.search_col.update_one(
        {"link_id": link_id},
        {"$set": {"caption": ""}}
    )

    await message.reply("🗑️ **Is file ke sabhi manual tags/captions delete kar diye gaye hain.**")
