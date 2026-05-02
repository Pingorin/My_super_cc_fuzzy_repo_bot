class script(object):
    # 👇 Is Footer ko apne hisab se edit karein
    CUSTOM_FOOTER = """
-----------------------------------------
<b>⚡ Powered by @ramsitaam</b>
<b>✨ Join for More: @YourChannel</b>
    """
    
    NEW_GROUP_TXT = """<b>🆕 New Group Added</b>

<b>Bot:</b> {}
<b>Title:</b> {}
<b>ID:</b> <code>{}</code>
<b>Username:</b> @{}
<b>Link:</b> {}
<b>Members:</b> {}
<b>Added By:</b> {}
"""

    # ==============================================================================
    # 💎 PREMIUM SYSTEM TEXTS
    # ==============================================================================

    # 1. UPSELL / BUY PREMIUM PITCH
    PREM_UPGRADE_TXT = """👋 Hello {mention},

🚨 Aap abhi **LIMITED** access use kar rahe hain (Ads + Slow Speed + Verification). 😒

👑 **Premium activate karke sab unlock karein:**
🚫 **NO ADS** – Zero interruption
⚡ **FAST DOWNLOAD** – No waiting
📂 **DIRECT FILES** – No links
🎬 **UNLIMITED MOVIES & SERIES**
💬 **PRIORITY SUPPORT** – Fast response

━━━━━━━━━━━━━━━━━━━━
🔥 1000+ users already upgraded
🛡️ Safe & trusted service

🎁 **FREE TRIAL AVAILABLE**
Trial ke liye `/myplan` use karein

🔥 **Limited-Time Offer** 🔥
Kabhi bhi khatam ho sakta hai!
━━━━━━━━━━━━━━━━━━━━"""

    # 2. PLANS & QR CODE
    PREM_PLANS_TXT = """⚡ **FLASH SALE: LIMITED TIME DISCOUNT** ⚡
🚨 Aaj upgrade nahi kiya toh kal Premium mehenga padega!

👑 **1 YEAR:** `₹200`
🔥 **1 MONTH:** `₹25`
⭐ **1 WEEK:** `₹10`
⏳ **1 DAY (Trial):** `₹1`

**🚀 Premium Benefits:**
🚫 No Ads | ⚡ Fast DL | 📂 Direct Files | 💬 Priority Support
━━━━━━━━━━━━━━━━━━━━
💳 **Payment Options:**
Scan the QR Code (GPay / PhonePe / Paytm)
Or use UPI ID: `{upi_id}` 👈

⚡ 2 min activation after screenshot
⏳ Delay karoge toh activation late hoga!"""

    # 3. CUSTOM PLAN
    PREM_CUSTOM_TXT = """👋 Hey {mention},
    
🎁 **OTHER PLAN / CUSTOM PLAN**
⏰ Customised Days
💸 According to days you choose

🏆 Agar aapko diye gaye plans ke alawa koi naya plan chahiye, toh aap direct owner se baat kar sakte hain.

👨‍💻 Niche diye gaye button par click karke owner ko message karein:
➛ Use `/plan` to see all our plans.
➛ Check your active plan by using: `/myplan`"""

    # 4. NO ACTIVE PLAN (MYPLAN)
    NO_PREM_TXT = """⚠️ **Aapka Koi Active Premium Plan Nahi Hai!**

Bina ads, bina verification — direct movies access chahiye? Aaj hi Premium lein aur apna time bachayein.

💡 Niche diye gaye button par click karke **5 Minute ka FREE Trial** try karein ya direct plan check karein!"""

    # 5. MYPLAN ACTIVE (PLAN PURCHASED)
    MYPLAN_ACTIVE_TXT = """🌟 **Aapka Premium Plan Active Hai!**

Aapne hamara premium membership liya hua hai aur aap ek VIP user hain.

👤 **User:** {mention}
📅 **Expiry Date:** `{expiry_date}`
🚀 **Status:** Active (No Ads/Direct Access)

Abhi bina kisi rukawat ke unlimited movies aur series ka maza lein!"""

    # 6. TRIAL ACTIVATION MESSAGE
    TRIAL_ACTIVE_TXT = """🎊 **Mubarak Ho! 5-Min Premium Trial Activate Ho Gaya Hai!** 🎊

Ab agle **5 Minute** tak aap hamare **VIP Member** hain! 🚀

🔥 **Ab aapko kya karna hai?**
1️⃣ Turant kisi bhi movie group mein jaaiye.
2️⃣ Apni manpasand movie ya series ka naam likhkar search karein.
3️⃣ Jaise hi bot link dega, uspar click karein—Aapko koi Ads ya Shortener nahi dikhega!

⏳ **Jaldi Karein:** Aapke paas sirf 5 minute hain, check karein hamari super-fast speed!"""
