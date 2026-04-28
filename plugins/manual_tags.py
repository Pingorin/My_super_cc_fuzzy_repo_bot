import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from database.ia_filterdb import Media
from info import ADMINS

logger = logging.getLogger(__name__)

async def get_active_db_collections(file_unique_id):
    """Helper function to find which DB contains the file"""
    file_data = await Media.data_col1.find_one({"file_unique_id": file_unique_id})
    if file_data: return file_data, Media.search_col1
    
    if Media.has_db2:
        file_data = await Media.data_col2.find_one({"file_unique_id": file_unique_id})
        if file_data: return file_data, Media.search_col2
        
    if Media.has_db3:
        file_data = await Media.data_col3.find_one({"file_unique_id": file_unique_id})
        if file_data: return file_data, Media.search_col3
        
    return None, None

@Client.on_message(filters.command("addtag") & filters.user(ADMINS))
async def add_manual_tag(client, message: Message):
    if not message.reply_to_message:
        return await message.reply("⚠️ **Kripya kisi video ya document par reply karke command dein.**")

    media = message.reply_to_message.document or message.reply_to_message.video
    if not media:
        return await message.reply("⚠️ **Ye koi video ya file nahi hai!**")

    tags_data = message.text.split(maxsplit=1)
    if len(tags_data) < 2:
        return await message.reply("⚠️ **Aapne koi tag nahi likha!**\n\n**Example:** `/addtag marvel, hindi`")

    new_tags = tags_data[1].strip()
    status_msg = await message.reply("⏳ **Tags add kar raha hoon...**")

    file_data, active_search_col = await get_active_db_collections(media.file_unique_id)
    
    if not file_data:
        return await status_msg.edit_text("❌ **Ye file database mein save nahi hai!**")

    link_id = file_data['_id']
    search_data = await active_search_col.find_one({"link_id": link_id})
    
    old_caption = search_data.get("caption") or ""
    file_name = search_data.get("file_name", "Unknown File")
    
    # ✅ FIX: Ye code Original Name aur Tags dono ko ek sath jod dega
    if "[Tags:" in old_caption:
        base_caption = old_caption.split("[Tags:")[0].strip()
        updated_caption = f"{base_caption} [Tags: {new_tags}]"
    else:
        updated_caption = f"{file_name} [Tags: {new_tags}]"

    await active_search_col.update_one(
        {"link_id": link_id},
        {"$set": {"caption": updated_caption}}
    )
    
    await status_msg.edit_text(
        f"✅ **Tags Successfully Added!**\n\n"
        f"📂 **Naya Caption:** `{updated_caption}`\n\n"
        f"*(Ab search me aur final file me dono naam dikhenge)*"
    )

@Client.on_message(filters.command("cleartags") & filters.user(ADMINS))
async def clear_manual_tag(client, message: Message):
    if not message.reply_to_message:
        return await message.reply("⚠️ **Kripya us file par reply karein.**")

    media = message.reply_to_message.document or message.reply_to_message.video
    if not media: return await message.reply("⚠️ **Ye koi video/file nahi hai!**")

    file_data, active_search_col = await get_active_db_collections(media.file_unique_id)
    
    if not file_data: return await message.reply("❌ **Database me nahi hai!**")

    link_id = file_data['_id']
    
    await active_search_col.update_one(
        {"link_id": link_id},
        {"$set": {"caption": ""}}
    )

    await message.reply("🗑️ **Is file ke sabhi manual tags aur caption delete kar diye gaye hain.**\nAb aap wapas `/addtag` use kar sakte hain.")
