#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zionix OSINT Bot - Complete Source Code
With all requested changes:
1. Removed zionix_chats and intelxGroup from force join
2. Added @encorexosint as force join channel
3. Added all new APIs (/pak, /ffinfo, /vnum, /rto, /leak, /imei, /ip)
4. Added AI API: https://ai-chat.apisimpacientes.workers.dev/
"""

import os
import json
import logging
import asyncio
import sqlite3
import re
import io
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dotenv import load_dotenv

import requests
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto, ChatPermissions, ChatMember,
    BotCommand, InlineQueryResultArticle, InputTextMessageContent
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ChatMemberHandler,
    ApplicationBuilder, InlineQueryHandler
)
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.error import BadRequest, TelegramError

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = "8509771819:AAHhktvIGstkDAwzfmSSdc9QfeA6Dzw05Ow"
BOT_USERNAME = os.getenv('BOT_USERNAME', '@zionXosintBot')
OWNER_ID = int(os.getenv('OWNER_ID', 8570940776))

# Three log channels
LOG_CHANNEL_REGISTRATION = os.getenv('LOG_CHANNEL_REGISTRATION', '@zionxosintbotlogs')
LOG_CHANNEL_SEARCH = os.getenv('LOG_CHANNEL_SEARCH', '@zbotslog')
LOG_CHANNEL_ERROR = os.getenv('LOG_CHANNEL_ERROR', '@zboterrorlog')

MIN_GROUP_MEMBERS = 25  # Minimum members required in group

# Global variable for force channels (will be loaded from database)
FORCE_CHANNELS = []

def load_force_channels_from_db():
    """Load force channels from database"""
    global FORCE_CHANNELS
    FORCE_CHANNELS = []
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT channel_name, username, invite_link, is_private, button_text FROM channels')
    rows = cursor.fetchall()
    
    for row in rows:
        FORCE_CHANNELS.append({
            "title": row['channel_name'],
            "username": row['username'],
            "invite_link": row['invite_link'],
            "is_private": bool(row['is_private']),
            "button_text": row['button_text'] or f"➕ ᴊᴏɪɴ {row['channel_name']}"
        })
    
    conn.close()
    logger.info(f"Loaded {len(FORCE_CHANNELS)} force channels from database")

# Primary force join channels (UPDATED: Removed zionix_chats and intelxGroup, added encorexosint)
PRIMARY_CHANNELS = [
    {"title": "ᴢɪᴏɴɪx ᴘᴏʀᴛᴀʟ", "username": "zionixportal", "invite_link": "https://t.me/zionixportal", "is_private": False, "button_text": "❄️ ᴊᴏɪɴ ᴢɪᴏɴɪx ᴘᴏʀᴛᴀʟ"},
    {"title": "ᴢɪᴏɴɪx ᴘᴏʀᴛᴀʟ 𝟸", "username": "zionix_portal", "invite_link": "https://t.me/zionix_portal", "is_private": False, "button_text": "❄️ ᴊᴏɪɴ ᴢɪᴏɴɪx ᴘᴏʀᴛᴀʟ 𝟸"},
    {"title": "ᴇɴᴄᴏʀᴇx ᴏꜱɪɴᴛ", "username": "encorexosint", "invite_link": "https://t.me/encorexosint", "is_private": False, "button_text": "❄️ ᴊᴏɪɴ ᴇɴᴄᴏʀᴇx ᴏꜱɪɴᴛ"}
]

# API endpoints (UPDATED: Added new APIs and AI API)
APIS = {
    # Existing APIs
    "num": "https://7.toxictanji0503.workers.dev/encorenum?num=",
    "aadhar": "https://7.toxictanji0503.workers.dev/ad?id=",
    "insta": "https://insta-profile-info-api.vercel.app/api/instagram.php?username=",
    "tg": "https://tginfo-zionix.vercel.app/user-details?user=",
    "vehicle": "https://vvvin-ng.vercel.app/lookup?rc=",
    "ip": "http://ip-api.com/json/",
    "ifsc": "https://ifsc.razorpay.com/",
    "gst": "https://gstlookup.hideme.eu.org/?gstNumber=",
    "mail": "https://mailinfo.vercel.app/info?mail=",
    "fam": "https://aetherosint.site/cutieee/fampay.php?key=FAIZAN&upi=",
    "ffuid": "https://anku-ffapi-inky.vercel.app/ff?uid=",
    
    # NEW APIs from your request
    "pak": "https://pak-info-api.vercel.app/api/lookup?query=",
    "ffinfo": "https://anku-ffapi-inky.vercel.app/ff?uid=",
    "vnum": "https://7.toxictanji0503.workers.dev/vnumowner?vehicle=",
    "rto": "https://api.globalcomputers.shop/?vehicle_number=",
    "leak": "https://aluuxidk.vercel.app/leak?key=6442851093:7ocdcXMi&id=",
    "imei": "https://imei-info.gauravyt566.workers.dev/?imei=",
    
    # AI API (NEW)
    "ai": "https://ai-chat.apisimpacientes.workers.dev/chat?model=copilot&prompt=",
    
    # Image API placeholder
    "img": "https://your-image-api.com/api?query="
}

# Database helper functions
def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    return conn

# Initialize SQLite database
def init_database():
    """Initialize SQLite database"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    # Create users table with credits
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_credit_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_banned BOOLEAN DEFAULT 0,
        ban_reason TEXT,
        total_searches INTEGER DEFAULT 0,
        credits INTEGER DEFAULT 5,
        referred_by INTEGER DEFAULT 0,
        referrals INTEGER DEFAULT 0,
        UNIQUE(user_id)
    )
    ''')
    
    # Create groups table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS groups (
        group_id INTEGER PRIMARY KEY,
        group_name TEXT,
        added_by INTEGER,
        add_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT 1,
        member_count INTEGER DEFAULT 0,
        last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(group_id)
    )
    ''')
    
    # Create search_logs table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS search_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        service TEXT,
        query TEXT,
        result TEXT,
        chat_type TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create admins table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        added_by INTEGER,
        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create channels table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS channels (
        channel_id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_name TEXT,
        username TEXT,
        invite_link TEXT,
        is_private BOOLEAN DEFAULT 0,
        button_text TEXT,
        added_by INTEGER,
        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT 1,
        UNIQUE(username)
    )
    ''')
    
    # Insert primary force channels
    for channel in PRIMARY_CHANNELS:
        cursor.execute('''
        INSERT OR IGNORE INTO channels (channel_name, username, invite_link, is_private, button_text, added_by)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (channel['title'], channel['username'], channel['invite_link'], 
              channel.get('is_private', False), channel.get('button_text', f"➕ ᴊᴏɪɴ {channel['title']}"), OWNER_ID))
    
    # Insert owner as admin
    cursor.execute('INSERT OR IGNORE INTO admins (user_id, username, added_by) VALUES (?, ?, ?)', 
                  (OWNER_ID, 'owner', OWNER_ID))
    
    conn.commit()
    conn.close()
    logger.info("✅ Database initialized successfully")
    
    # Load force channels from database
    load_force_channels_from_db()

# Initialize database
init_database()


def add_or_update_user(user_id: int, username: str, first_name: str, last_name: str = "", referred_by: int = 0):
    """Add or update user in database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT user_id, credits FROM users WHERE user_id = ?', (user_id,))
    existing_user = cursor.fetchone()
    
    if not existing_user:
        # New user
        cursor.execute('''
        INSERT INTO users (user_id, username, first_name, last_name, join_date, last_active, last_credit_date, credits, referred_by)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 5, ?)
        ''', (user_id, username or "", first_name, last_name or "", referred_by))
        
        # Update referrer's credits if exists
        if referred_by and referred_by != user_id:
            cursor.execute('''
            UPDATE users SET credits = credits + 10, referrals = referrals + 1 
            WHERE user_id = ?
            ''', (referred_by,))
        
        is_new_user = True
    else:
        # Update existing user
        cursor.execute('''
        UPDATE users SET username = ?, first_name = ?, last_name = ?, last_active = CURRENT_TIMESTAMP
        WHERE user_id = ?
        ''', (username or "", first_name, last_name or "", user_id))
        is_new_user = False
    
    conn.commit()
    conn.close()
    return is_new_user

def add_or_update_group(group_id: int, group_name: str, added_by: int, member_count: int = 0):
    """Add or update group in database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT group_id FROM groups WHERE group_id = ?', (group_id,))
    existing_group = cursor.fetchone()
    
    if not existing_group:
        cursor.execute('''
        INSERT INTO groups (group_id, group_name, added_by, add_date, is_active, member_count, last_checked)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, 1, ?, CURRENT_TIMESTAMP)
        ''', (group_id, group_name, added_by, member_count))
        is_new_group = True
    else:
        cursor.execute('''
        UPDATE groups SET group_name = ?, added_by = ?, member_count = ?, last_checked = CURRENT_TIMESTAMP
        WHERE group_id = ?
        ''', (group_name, added_by, member_count, group_id))
        is_new_group = False
    
    conn.commit()
    conn.close()
    return is_new_group

def update_group_member_count(group_id: int, member_count: int):
    """Update group member count"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE groups SET member_count = ?, last_checked = CURRENT_TIMESTAMP
    WHERE group_id = ?
    ''', (member_count, group_id))
    conn.commit()
    conn.close()

def update_daily_credits(user_id: int):
    """Update daily credits for user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT last_credit_date, credits FROM users WHERE user_id = ?', (user_id,))
    user_data = cursor.fetchone()
    
    if user_data:
        last_credit_date = datetime.strptime(user_data['last_credit_date'], '%Y-%m-%d %H:%M:%S')
        if (datetime.now() - last_credit_date).days >= 1:
            cursor.execute('''
            UPDATE users SET credits = credits + 5, last_credit_date = CURRENT_TIMESTAMP
            WHERE user_id = ?
            ''', (user_id,))
            conn.commit()
            conn.close()
            return True
    conn.close()
    return False

def get_user_credits(user_id: int, chat_type: str = "private") -> int:
    """Get user credits"""
    if chat_type != "private":
        return 999999  # Unlimited credits in groups
    
    update_daily_credits(user_id)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT credits FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return result['credits']
    return 0

def use_credits(user_id: int, amount: int = 1, chat_type: str = "private") -> bool:
    """Use user credits"""
    if chat_type != "private":
        return True  # Unlimited credits in groups
    
    update_daily_credits(user_id)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT credits FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if result and result['credits'] >= amount:
        cursor.execute('UPDATE users SET credits = credits - ? WHERE user_id = ?', (amount, user_id))
        conn.commit()
        conn.close()
        return True
    
    conn.close()
    return False

def log_search(user_id: int, service: str, query: str, result: str = "", chat_type: str = "private"):
    """Log search to database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO search_logs (user_id, service, query, result, chat_type)
    VALUES (?, ?, ?, ?, ?)
    ''', (user_id, service, query, result[:500], chat_type))
    
    cursor.execute('''
    UPDATE users SET total_searches = total_searches + 1, last_active = CURRENT_TIMESTAMP
    WHERE user_id = ?
    ''', (user_id,))
    
    conn.commit()
    conn.close()

def get_admins() -> List[int]:
    """Get all admin user IDs"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM admins')
    admins = [row[0] for row in cursor.fetchall()]
    conn.close()
    return admins

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    admins = get_admins()
    return user_id == OWNER_ID or user_id in admins

def get_user_count():
    """Get total number of users"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) as count FROM users WHERE is_banned = 0')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_group_count():
    """Get total number of groups"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) as count FROM groups WHERE is_active = 1')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_total_searches():
    """Get total number of searches"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) as count FROM search_logs')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_user_stats(user_id: int):
    """Get user statistics"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT total_searches, join_date, last_active, credits, referrals, referred_by
    FROM users WHERE user_id = ?
    ''', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result

async def send_log_to_channel(context: ContextTypes.DEFAULT_TYPE, message: str, log_type: str = "registration"):
    """Send log message to appropriate log channel"""
    try:
        if log_type == "search":
            chat_id = LOG_CHANNEL_SEARCH
        elif log_type == "error":
            chat_id = LOG_CHANNEL_ERROR
        else:
            chat_id = LOG_CHANNEL_REGISTRATION
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Failed to send log to channel: {e}")

async def check_group_member_count(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> Tuple[bool, int]:
    """Check if group has minimum required members"""
    try:
        member_count = await context.bot.get_chat_member_count(chat_id)
        update_group_member_count(chat_id, member_count)
        
        if member_count < MIN_GROUP_MEMBERS:
            return False, member_count
        return True, member_count
    except Exception as e:
        logger.error(f"Error checking group member count: {e}")
        return False, 0

async def check_channel_membership(user_id: int, channel_info: dict, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user is member of a channel"""
    try:
        username = channel_info.get('username')
        if not username:
            return False
            
        # Remove @ if present
        username = username.replace('@', '')
        
        try:
            chat_member = await context.bot.get_chat_member(f"@{username}", user_id)
            return chat_member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
        except Exception as e:
            logger.error(f"Error checking membership for @{username}: {e}")
            return False
    except Exception as e:
        logger.error(f"Error checking channel membership: {e}")
        return False

async def check_all_channels(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> Tuple[bool, List[dict]]:
    """Check if user has joined all force channels"""
    not_joined = []
    
    for channel in FORCE_CHANNELS:
        is_member = await check_channel_membership(user_id, channel, context)
        if not is_member:
            not_joined.append(channel)
    
    return len(not_joined) == 0, not_joined

async def force_join_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user has joined required channels"""
    user = update.effective_user
    
    if is_admin(user.id):
        return True
    
    all_joined, not_joined = await check_all_channels(user.id, context)
    
    if not all_joined:
        chat = update.effective_chat
        chat_id = chat.id if chat else user.id
        
        keyboard = []
        for channel in not_joined:
            button_text = channel.get('button_text', f"➕ ᴊᴏɪɴ {channel['title']}")
            keyboard.append([InlineKeyboardButton(button_text, url=channel['invite_link'])])
        
        keyboard.append([InlineKeyboardButton("✅ ɪ'ᴠᴇ ᴊᴏɪɴᴇᴅ", callback_data=f"verify_join_{chat_id}_{user.id}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = f"""
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>⚠️ ᴄʜᴀɴɴᴇʟ ᴍᴇᴍʙᴇʀꜱʜɪᴘ ʀᴇǫᴜɪʀᴇᴅ</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>

👤 <b>ᴜꜱᴇʀ:</b> {user.mention_html()}

<b>ʏᴏᴜ ᴍᴜꜱᴛ ᴊᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟꜱ ᴛᴏ ᴜꜱᴇ ᴛʜɪꜱ ʙᴏᴛ.</b>

<b>ᴘʟᴇᴀꜱᴇ ᴊᴏɪɴ ᴀʟʟ ᴄʜᴀɴɴᴇʟꜱ ʙᴇʟᴏᴡ ᴀɴᴅ ᴄʟɪᴄᴋ 'ɪ'ᴠᴇ ᴊᴏɪɴᴇᴅ':</b>
"""
        
        try:
            video_url = "https://t.me/imgsrcvvv/3"
            if update.message:
                await update.message.reply_video(
                    video=video_url,
                    caption=message_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
            elif update.callback_query:
                await update.callback_query.message.reply_video(
                    video=video_url,
                    caption=message_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
        except:
            if update.message:
                await update.message.reply_text(
                    message_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
            elif update.callback_query:
                await update.callback_query.message.reply_text(
                    message_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
        return False
    
    return True

def format_json_response(data: dict, max_length: int = 3000) -> Tuple[str, str]:
    """Format JSON data in code blocks and return both truncated and full versions"""
    try:
        formatted = json.dumps(data, indent=2, ensure_ascii=False)
        full_text = f"<pre><code>{formatted}</pre></code>"
        
        # Truncate if too long
        if len(full_text) > max_length:
            truncated = full_text[:max_length] + "\n...\n```\n\n📁 *Results truncated. Full results sent as file below.*"
            return truncated, full_text
        else:
            return full_text, full_text
    except Exception as e:
        error_text = f"<pre><code>{str(data)}</pre></code>"
        if len(error_text) > max_length:
            truncated = error_text[:max_length] + "\n...\n```\n\n📁 *Results truncated. Full results sent as file below.*"
            return truncated, error_text
        return error_text, error_text

async def send_api_result(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                         service: str, query: str, result: dict):
    """Send formatted API result"""
    user = update.effective_user
    chat = update.effective_chat
    chat_type = chat.type if chat else "private"
    
    # Check credits
    if not use_credits(user.id, 1, chat_type):
        await update.message.reply_text(
            "❌ <b>ɪɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ ᴄʀᴇᴅɪᴛꜱ!</b>\n\nʏᴏᴜ ɴᴇᴇᴅ ᴍᴏʀᴇ ᴄʀᴇᴅɪᴛꜱ ᴛᴏ ᴜꜱᴇ ᴛʜɪꜱ ꜱᴇʀᴠɪᴄᴇ.\nᴜꜱᴇ /credits ᴛᴏ ᴄʜᴇᴄᴋ ʏᴏᴜʀ ʙᴀʟᴀɴᴄᴇ.",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Update user and log search
    is_new_user = add_or_update_user(user.id, user.username, user.first_name, user.last_name or "")
    log_search(user.id, service, query, json.dumps(result)[:500], chat_type)
    
    # Send search log
    search_log = f"""
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>🔍 ꜱᴇᴀʀᴄʜ ʟᴏɢ</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>

<b>📱 ꜱᴇʀᴠɪᴄᴇ:</b> {service.upper()}
<b>👤 ᴜꜱᴇʀ:</b> {user.mention_html()}
<b>🆔 ɪᴅ:</b> <code>{user.id}</code>
<b>🔎 ǫᴜᴇʀʏ:</b> <code>{query}</code>
<b>💬 ᴄʜᴀᴛ:</b> {chat_type}
<b>📅 ᴛɪᴍᴇ:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>
"""
    await send_log_to_channel(context, search_log, "search")
    
    # Service titles
    service_titles = {
        "num": "📱 ᴍᴏʙɪʟᴇ ɴᴜᴍʙᴇʀ ʟᴏᴏᴋᴜᴘ",
        "aadhar": "🆔 ᴀᴀᴅʜᴀʀ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ",
        "ip": "🌐 ɪᴘ ᴀᴅᴅʀᴇꜱꜱ ɪɴꜰᴏʀᴍᴀᴛɪᴏɴ",
        "vehicle": "🚗 ᴠᴇʜɪᴄʟᴇ ᴅᴇᴛᴀɪʟꜱ",
        "tg": "📱 ᴛᴇʟᴇɢʀᴀᴍ ᴜꜱᴇʀ ɪɴꜰᴏ",
        "insta": "📸 ɪɴꜱᴛᴀɢʀᴀᴍ ᴘʀᴏꜰɪʟᴇ",
        "gst": "🏢 ɢꜱᴛ ᴅᴇᴛᴀɪʟꜱ",
        "ifsc": "🏦 ɪꜰꜱᴄ ᴄᴏᴅᴇ ɪɴꜰᴏʀᴍᴀᴛɪᴏɴ",
        "ai": "🤖 ᴀɪ ᴀꜱꜱɪꜱᴛᴀɴᴛ",
        "img": "🖼 ɪᴍᴀɢᴇ ꜱᴇᴀʀᴄʜ",
        "mail": "📧 ᴇᴍᴀɪʟ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ",
        "fam": "👨‍👩‍👧‍👦 ꜰᴀᴍɪʟʏ ᴅᴇᴛᴀɪʟꜱ",
        "ffuid": "🎮 ꜰʀᴇᴇ ꜰɪʀᴇ ᴜꜱᴇʀ ɪᴅ",
        "pak": "🇵🇰 ᴘᴀᴋɪꜱᴛᴀɴ ɴᴜᴍʙᴇʀ ʟᴏᴏᴋᴜᴘ",
        "ffinfo": "🎮 ꜰʀᴇᴇ ꜰɪʀᴇ ɪɴꜰᴏ",
        "vnum": "🚗 ᴠᴇʜɪᴄʟᴇ ɴᴜᴍʙᴇʀ ᴏᴡɴᴇʀ",
        "rto": "🏢 ʀᴛᴏ ᴠᴇʜɪᴄʟᴇ ɪɴꜰᴏ",
        "leak": "🔓 ʟᴇᴀᴋᴇᴅ ᴅᴀᴛᴀ ꜱᴇᴀʀᴄʜ",
        "imei": "📱 ɪᴍᴇɪ ɴᴜᴍʙᴇʀ ʟᴏᴏᴋᴜᴘ"
    }
    
    # Format result - get both truncated and full versions
    truncated_result, full_result = format_json_response(result)
    
    message_text = f"""
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>{service_titles.get(service, 'ꜱᴇᴀʀᴄʜ ʀᴇꜱᴜʟᴛꜱ')}</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>

{truncated_result}

<code>───────────────────────</code>
<b>👤 ʀᴇǫᴜᴇꜱᴛᴇᴅ ʙʏ:</b> {user.mention_html()}
<b>🔍 ǫᴜᴇʀʏ:</b> <code>{query}</code>
<b>⏰ ᴛɪᴍᴇ:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>
"""
    
    # Create buttons with inline buttons
    keyboard = [
        [
            InlineKeyboardButton("🤖 ᴜꜱᴇ ᴍᴇ ʜᴇʀᴇ", url="https://t.me/zionix_chats"),
            InlineKeyboardButton("📨 ᴜꜱᴇ ɪɴ ᴘᴍ", url=f"https://t.me/{context.bot.username}?start")
        ],
        [
            InlineKeyboardButton("➕ ᴀᴅᴅ ᴛᴏ ɢʀᴏᴜᴘ", url=f"https://t.me/{context.bot.username}?startgroup=true"),
            InlineKeyboardButton("💰 ᴄʀᴇᴅɪᴛꜱ", callback_data="check_credits")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send message
    try:
        if chat_type == "private":
            photo_url = "https://t.me/imgsrcvvv/2"
            await update.message.reply_photo(
                photo=photo_url,
                caption=message_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                text=message_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        
        # If result was truncated, send full result as file
        if truncated_result != full_result:
            # Create file in memory
            file_content = json.dumps(result, indent=2, ensure_ascii=False)
            file_bytes = io.BytesIO(file_content.encode('utf-8'))
            file_bytes.name = f"{service}_{query}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            file_caption = f"""
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>📁 ꜰᴜʟʟ ʀᴇꜱᴜʟᴛꜱ ꜰɪʟᴇ</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>

<b>📱 ꜱᴇʀᴠɪᴄᴇ:</b> {service.upper()}
<b>🔍 ǫᴜᴇʀʏ:</b> <code>{query}</code>
<b>👤 ʀᴇǫᴜᴇꜱᴛᴇᴅ ʙʏ:</b> {user.mention_html()}
<b>📊 ʀᴇꜱᴜʟᴛ ꜱɪᴢᴇ:</b> {len(file_content):,} ᴄʜᴀʀᴀᴄᴛᴇʀꜱ
"""
            
            await update.message.reply_document(
                document=file_bytes,
                caption=file_caption,
                parse_mode=ParseMode.HTML
            )
            
    except Exception as e:
        logger.error(f"Error sending result: {e}")
        await update.message.reply_text(
            text=message_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    chat = update.effective_chat
    
    # Check for referral
    referred_by = 0
    if context.args and len(context.args) > 0:
        try:
            referred_by = int(context.args[0])
        except:
            pass
    
    # Add/update user with referral
    is_new_user = add_or_update_user(user.id, user.username, user.first_name, user.last_name or "", referred_by)
    
    # Send registration log
    if is_new_user:
        reg_log = f"""
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>🆕 ɴᴇᴡ ᴜꜱᴇʀ ꜱᴛᴀʀᴛᴇᴅ</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>

<b>👤 ᴜꜱᴇʀ:</b> {user.mention_html()}
<b>🆔 ɪᴅ:</b> <code>{user.id}</code>
<b>👤 ᴜꜱᴇʀɴᴀᴍᴇ:</b> @{user.username if user.username else 'ɴ/ᴀ'}
<b>📅 ᴅᴀᴛᴇ:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>
<b>👥 ᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ:</b> <code>{get_user_count()}</code>
<b>🎯 ʀᴇꜰᴇʀʀᴇᴅ ʙʏ:</b> <code>{referred_by if referred_by else 'ɴᴏɴᴇ'}</code>
"""
        await send_log_to_channel(context, reg_log, "registration")
    
    if chat.type == "private":
        # Check force join
        all_joined, not_joined = await check_all_channels(user.id, context)
        
        if not all_joined:
            # Send video with join buttons
            keyboard = []
            for channel in not_joined:
                button_text = channel.get('button_text', f"➕ ᴊᴏɪɴ {channel['title']}")
                keyboard.append([InlineKeyboardButton(button_text, url=channel['invite_link'])])
            
            keyboard.append([InlineKeyboardButton("✅ ɪ'ᴠᴇ ᴊᴏɪɴᴇᴅ", callback_data=f"verify_join_{chat.id}_{user.id}")])
            reply_markup = InlineKeyboardMarkup(keyboard)
           
            caption = f"""
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>👋 ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴢɪᴏɴɪx ᴏꜱɪɴᴛ ʙᴏᴛ</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>

<b>ᴘʟᴇᴀꜱᴇ ᴊᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟꜱ ᴛᴏ ᴜꜱᴇ ᴛʜᴇ ʙᴏᴛ:</b>
"""
            
            try:
                await update.message.reply_video(
                    video="https://t.me/imgsrcvvv/3",
                    caption=caption,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
            except:
                await update.message.reply_text(
                    caption,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
            return
        
        # Send welcome video with inline buttons
        welcome_text = f"""
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>🪬 ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴢɪᴏɴɪx ᴏꜱɪɴᴛ ʙᴏᴛ</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>

<b>🌟 ꜰᴇᴀᴛᴜʀᴇꜱ:</b>
• 📱 ᴘʜᴏɴᴇ ɴᴜᴍʙᴇʀ ʟᴏᴏᴋᴜᴘ
• 🆔 ᴀᴀᴅʜᴀʀ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ
• 🌐 ɪᴘ ɪɴꜰᴏʀᴍᴀᴛɪᴏɴ
• 🚗 ᴠᴇʜɪᴄʟᴇ ᴅᴇᴛᴀɪʟꜱ
• 📱 ᴛᴇʟᴇɢʀᴀᴍ ᴜꜱᴇʀ ɪɴꜰᴏ
• 📸 ɪɴꜱᴛᴀɢʀᴀᴍ ᴘʀᴏꜰɪʟᴇ
• 🏢 ɢꜱᴛ ᴅᴇᴛᴀɪʟꜱ
• 🏦 ɪꜰꜱᴄ ᴄᴏᴅᴇ ʟᴏᴏᴋᴜᴘ
• 🤖 ᴀɪ ᴀꜱꜱɪꜱᴛᴀɴᴛ
• 🖼 ɪᴍᴀɢᴇ ꜱᴇᴀʀᴄʜ
• 📧 ᴇᴍᴀɪʟ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ
• 👨‍👩‍👧‍👦 ꜰᴀᴍɪʟʏ ᴅᴇᴛᴀɪʟꜱ
• 🎮 ꜰʀᴇᴇ ꜰɪʀᴇ ᴜꜱᴇʀ ɪᴅ
• 🇵🇰 ᴘᴀᴋɪꜱᴛᴀɴ ɴᴜᴍʙᴇʀ
• 🎮 ꜰʀᴇᴇ ꜰɪʀᴇ ɪɴꜰᴏ
• 🚗 ᴠᴇʜɪᴄʟᴇ ᴏᴡɴᴇʀ
• 🏢 ʀᴛᴏ ᴠᴇʜɪᴄʟᴇ
• 🔓 ʟᴇᴀᴋᴇᴅ ᴅᴀᴛᴀ
• 📱 ɪᴍᴇɪ ɴᴜᴍʙᴇʀ

<b>💰 ᴄʀᴇᴅɪᴛ ꜱʏꜱᴛᴇᴍ:</b>
• 🎁 5 ᴅᴀɪʟʏ ᴄʀᴇᴅɪᴛꜱ
• 🤝 10 ᴄʀᴇᴅɪᴛꜱ ᴘᴇʀ ʀᴇꜰᴇʀʀᴀʟ
• 👥 ᴜɴʟɪᴍɪᴛᴇᴅ ɪɴ ɢʀᴏᴜᴘꜱ

<b>🛠 ᴜꜱᴇ /help ꜰᴏʀ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅꜱ</b>
<b>🔗 ʀᴇꜰᴇʀʀᴀʟ ʟɪɴᴋ:</b> <code>https://t.me/{context.bot.username}?start={user.id}</code>
"""
        
        keyboard = [
            [
                InlineKeyboardButton("🔍 ꜱᴇᴀʀᴄʜ ꜱᴇʀᴠɪᴄᴇꜱ", callback_data="search_services"),
                InlineKeyboardButton("💰 ᴄʀᴇᴅɪᴛꜱ", callback_data="check_credits")
            ],
            [
                InlineKeyboardButton("🤖 ᴜꜱᴇ ᴍᴇ ʜᴇʀᴇ", url="https://t.me/zionix_chats"),
                InlineKeyboardButton("📨 ᴜꜱᴇ ɪɴ ᴘᴍ", url=f"https://t.me/{context.bot.username}?start")
            ],
            [
                InlineKeyboardButton("➕ ᴀᴅᴅ ᴛᴏ ɢʀᴏᴜᴘ", url=f"https://t.me/{context.bot.username}?startgroup=true"),
                InlineKeyboardButton("📊 ꜱᴛᴀᴛꜱ", callback_data="check_stats")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await update.message.reply_video(
                video="https://t.me/imgsrcvvv/3",
                caption=welcome_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
        except:
            await update.message.reply_photo(
                photo="https://t.me/imgsrcvvv/2",
                caption=welcome_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
    
    else:
        # Group chat - check minimum members
        has_min_members, member_count = await check_group_member_count(context, chat.id)
        
        if not has_min_members and member_count > 0:
            await update.message.reply_text(
                text=f"❌ <b>ᴛʜɪꜱ ɢʀᴏᴜᴘ ʜᴀꜱ ᴏɴʟʏ {member_count} ᴍᴇᴍʙᴇʀꜱ.</b>\n\n⚠️ <b>ᴍɪɴɪᴍᴜᴍ {MIN_GROUP_MEMBERS} ᴍᴇᴍʙᴇʀꜱ ʀᴇǫᴜɪʀᴇᴅ ᴛᴏ ᴜꜱᴇ ᴛʜɪꜱ ʙᴏᴛ.</b>\n\nᴘʟᴇᴀꜱᴇ ᴀᴅᴅ ᴍᴏʀᴇ ᴍᴇᴍʙᴇʀꜱ ᴀɴᴅ ᴛʀʏ ᴀɢᴀɪɴ.",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Add/update group
        is_new_group = add_or_update_group(chat.id, chat.title, user.id, member_count)
        
        # Send group registration log
        if is_new_group:
            group_log = f"""
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>🆕 ʙᴏᴛ ᴀᴅᴅᴇᴅ ᴛᴏ ɢʀᴏᴜᴘ</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>

<b>👥 ɢʀᴏᴜᴘ:</b> {chat.title}
<b>🆔 ɪᴅ:</b> <code>{chat.id}</code>
<b>👤 ᴀᴅᴅᴇᴅ ʙʏ:</b> {user.mention_html()}
<b>👥 ᴍᴇᴍʙᴇʀꜱ:</b> <code>{member_count}</code>
<b>📅 ᴅᴀᴛᴇ:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>
<b>👥 ᴛᴏᴛᴀʟ ɢʀᴏᴜᴘꜱ:</b> <code>{get_group_count()}</code>
"""
            await send_log_to_channel(context, group_log, "registration")
        
        # Group welcome message with inline buttons
        group_welcome = f"""
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>🎬 ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴢɪᴏɴɪx ᴏꜱɪɴᴛ ʙᴏᴛ</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>

<b>👤 ᴜꜱᴇʀ:</b> {user.mention_html()}

<b>🌟 ꜰᴇᴀᴛᴜʀᴇꜱ:</b>
• 📱 ᴘʜᴏɴᴇ ɴᴜᴍʙᴇʀ ʟᴏᴏᴋᴜᴘ
• 🆔 ᴀᴀᴅʜᴀʀ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ
• 🌐 ɪᴘ ɪɴꜰᴏʀᴍᴀᴛɪᴏɴ
• 🚗 ᴠᴇʜɪᴄʟᴇ ᴅᴇᴛᴀɪʟꜱ
• 📱 ᴛᴇʟᴇɢʀᴀᴍ ᴜꜱᴇʀ ɪɴꜰᴏ
• 📸 ɪɴꜱᴛᴀɢʀᴀᴍ ᴘʀᴏꜰɪʟᴇ
• 🏢 ɢꜱᴛ ᴅᴇᴛᴀɪʟꜱ
• 🏦 ɪꜰꜱᴄ ᴄᴏᴅᴇ ʟᴏᴏᴋᴜᴘ
• 🤖 ᴀɪ ᴀꜱꜱɪꜱᴛᴀɴᴛ
• 🖼 ɪᴍᴀɢᴇ ꜱᴇᴀʀᴄʜ
• 📧 ᴇᴍᴀɪʟ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ
• 👨‍👩‍👧‍👦 ꜰᴀᴍɪʟʏ ᴅᴇᴛᴀɪʟꜱ
• 🎮 ꜰʀᴇᴇ ꜰɪʀᴇ ᴜꜱᴇʀ ɪᴅ
• 🇵🇰 ᴘᴀᴋɪꜱᴛᴀɴ ɴᴜᴍʙᴇʀ
• 🎮 ꜰʀᴇᴇ ꜰɪʀᴇ ɪɴꜰᴏ
• 🚗 ᴠᴇʜɪᴄʟᴇ ᴏᴡɴᴇʀ
• 🏢 ʀᴛᴏ ᴠᴇʜɪᴄʟᴇ
• 🔓 ʟᴇᴀᴋᴇᴅ ᴅᴀᴛᴀ
• 📱 ɪᴍᴇɪ ɴᴜᴍʙᴇʀ

<b>👥 ᴜɴʟɪᴍɪᴛᴇᴅ ᴄʀᴇᴅɪᴛꜱ ɪɴ ɢʀᴏᴜᴘꜱ</b>
<b>🛠 ᴜꜱᴇ /help ꜰᴏʀ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅꜱ</b>
"""
        
        keyboard = [
            [
                InlineKeyboardButton("🔍 ꜱᴇᴀʀᴄʜ ꜱᴇʀᴠɪᴄᴇꜱ", callback_data="search_services"),
                InlineKeyboardButton("🤖 ᴜꜱᴇ ᴍᴇ ʜᴇʀᴇ", url="https://t.me/zionix_chats")
            ],
            [
                InlineKeyboardButton("📨 ᴜꜱᴇ ɪɴ ᴘᴍ", url=f"https://t.me/{context.bot.username}?start"),
                InlineKeyboardButton("➕ ᴀᴅᴅ ᴛᴏ ɢʀᴏᴜᴘ", url=f"https://t.me/{context.bot.username}?startgroup=true")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            text=group_welcome,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )

# ADD CHANNEL COMMAND - FIXED VERSION
async def addchannel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add new force join channel - FIXED WORKING VERSION"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ <b>ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ.</b>", parse_mode=ParseMode.HTML)
        return
    
    if not context.args or len(context.args) < 3:
        help_text = """
<b>📝 ᴀᴅᴅ ɴᴇᴡ ꜰᴏʀᴄᴇ ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ</b>

<code>/addchannel username "Channel Title" invite_link [button_text] [is_private]</code>

<b>📌 ᴘᴀʀᴀᴍᴇᴛᴇʀꜱ:</b>
• <code>username</code> - ᴄʜᴀɴɴᴇʟ ᴜꜱᴇʀɴᴀᴍᴇ (ᴡɪᴛʜᴏᴜᴛ @)
• <code>Channel Title</code> - ᴄʜᴀɴɴᴇʟ ɴᴀᴍᴇ (ɪɴ ǫᴜᴏᴛᴇꜱ)
• <code>invite_link</code> - ɪɴᴠɪᴛᴇ ʟɪɴᴋ
• <code>button_text</code> - (ᴏᴘᴛɪᴏɴᴀʟ) ʙᴜᴛᴛᴏɴ ᴛᴇxᴛ
• <code>is_private</code> - (ᴏᴘᴛɪᴏɴᴀʟ) 1 ꜰᴏʀ ᴘʀɪᴠᴀᴛᴇ, 0 ꜰᴏʀ ᴘᴜʙʟɪᴄ (ᴅᴇꜰᴀᴜʟᴛ: 0)

<b>📋 ᴇxᴀᴍᴘʟᴇꜱ:</b>
<code>/addchannel mychannel "ᴍʏ ᴄʜᴀɴɴᴇʟ" https://t.me/mychannel</code>
<code>/addchannel privatechannel "ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀɴɴᴇʟ" https://t.me/privatechannel "➕ ᴊᴏɪɴ ᴘʀɪᴠᴀᴛᴇ" 1</code>
"""
        await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)
        return
    
    # Parse arguments
    username = context.args[0].replace('@', '')  # Remove @ if present
    
    # Find channel title (it's in quotes)
    args_text = ' '.join(context.args[1:])
    title_match = re.search(r'"([^"]+)"', args_text)
    
    if not title_match:
        await update.message.reply_text("❌ <b>ᴘʟᴇᴀꜱᴇ ᴇɴᴄʟᴏꜱᴇ ᴄʜᴀɴɴᴇʟ ᴛɪᴛʟᴇ ɪɴ ǫᴜᴏᴛᴇꜱ (\"\")</b>", parse_mode=ParseMode.HTML)
        return
    
    channel_title = title_match.group(1)
    
    # Remove the title from args_text
    remaining_text = args_text.replace(title_match.group(0), '').strip()
    remaining_args = remaining_text.split() if remaining_text else []
    
    if len(remaining_args) < 1:
        await update.message.reply_text("❌ <b>ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ɪɴᴠɪᴛᴇ ʟɪɴᴋ</b>", parse_mode=ParseMode.HTML)
        return
    
    invite_link = remaining_args[0]
    button_text = None
    is_private = 0
    
    # Parse optional parameters
    if len(remaining_args) > 1:
        # Check if next arg is button_text (might be in quotes)
        next_arg = remaining_args[1]
        if next_arg.startswith('"'):
            # Button text is in quotes
            button_match = re.search(r'"([^"]+)"', ' '.join(remaining_args[1:]))
            if button_match:
                button_text = button_match.group(1)
                # Remove button text from remaining args
                remaining_text_after_button = ' '.join(remaining_args[1:]).replace(button_match.group(0), '').strip()
                remaining_args_after_button = remaining_text_after_button.split() if remaining_text_after_button else []
                
                # Check for is_private
                if remaining_args_after_button:
                    try:
                        is_private = int(remaining_args_after_button[0])
                    except:
                        pass
        else:
            # Check if it's is_private flag
            try:
                is_private = int(next_arg)
            except:
                # It's button_text without quotes
                button_text = next_arg
                
                # Check for is_private after button_text
                if len(remaining_args) > 2:
                    try:
                        is_private = int(remaining_args[2])
                    except:
                        pass
    
    # Default button text if not provided
    if not button_text:
        button_text = f"➕ ᴊᴏɪɴ {channel_title}"
    
    # Validate invite link
    if not invite_link.startswith('https://t.me/'):
        await update.message.reply_text("❌ <b>ɪɴᴠᴀʟɪᴅ ɪɴᴠɪᴛᴇ ʟɪɴᴋ. ᴍᴜꜱᴛ ꜱᴛᴀʀᴛ ᴡɪᴛʜ https://t.me/</b>", parse_mode=ParseMode.HTML)
        return
    
    # Check if channel already exists
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT channel_id FROM channels WHERE username = ?', (username,))
    existing = cursor.fetchone()
    
    if existing:
        await update.message.reply_text(f"❌ <b>ᴄʜᴀɴɴᴇʟ @{username} ᴀʟʀᴇᴀᴅʏ ᴇxɪꜱᴛꜱ!</b>", parse_mode=ParseMode.HTML)
        conn.close()
        return
    
    # Add channel to database
    try:
        cursor.execute('''
        INSERT INTO channels (channel_name, username, invite_link, is_private, button_text, added_by)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (channel_title, username, invite_link, is_private, button_text, user_id))
        
        conn.commit()
        conn.close()
        
        # Reload force channels cache
        load_force_channels_from_db()
        
        success_msg = f"""
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>✅ ᴄʜᴀɴɴᴇʟ ᴀᴅᴅᴇᴅ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ!</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>

<b>📢 ᴄʜᴀɴɴᴇʟ:</b> {channel_title}
<b>👤 ᴜꜱᴇʀɴᴀᴍᴇ:</b> @{username}
<b>🔗 ɪɴᴠɪᴛᴇ ʟɪɴᴋ:</b> {invite_link}
<b>🔒 ᴘʀɪᴠᴀᴛᴇ:</b> {'Yes' if is_private else 'No'}
<b>🔘 ʙᴜᴛᴛᴏɴ ᴛᴇxᴛ:</b> {button_text}
<b>👤 ᴀᴅᴅᴇᴅ ʙʏ:</b> {update.effective_user.mention_html()}
<b>📅 ᴛɪᴍᴇ:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
<b>📊 ᴛᴏᴛᴀʟ ᴄʜᴀɴɴᴇʟꜱ:</b> {len(FORCE_CHANNELS)}
"""
        await update.message.reply_text(success_msg, parse_mode=ParseMode.HTML)
        
        # Send to log channel
        await send_log_to_channel(context, success_msg, "registration")
        
    except Exception as e:
        conn.close()
        await update.message.reply_text(f"❌ <b>ᴇʀʀᴏʀ ᴀᴅᴅɪɴɢ ᴄʜᴀɴɴᴇʟ:</b> {str(e)}", parse_mode=ParseMode.HTML)

async def listchannels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all force join channels"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ <b>ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ.</b>", parse_mode=ParseMode.HTML)
        return
    
    if not FORCE_CHANNELS:
        await update.message.reply_text("📭 <b>ɴᴏ ᴄʜᴀɴɴᴇʟꜱ ᴄᴏɴꜰɪɢᴜʀᴇᴅ.</b>", parse_mode=ParseMode.HTML)
        return
    
    channels_text = "<b>📢 ꜰᴏʀᴄᴇ ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟꜱ:</b>\n\n"
    
    for i, channel in enumerate(FORCE_CHANNELS, 1):
        channels_text += f"""<b>{i}. {channel['title']}</b>
├ <b>ᴜꜱᴇʀɴᴀᴍᴇ:</b> @{channel['username']}
├ <b>ʟɪɴᴋ:</b> {channel['invite_link']}
├ <b>ᴘʀɪᴠᴀᴛᴇ:</b> {'✅' if channel.get('is_private') else '❌'}
└ <b>ʙᴜᴛᴛᴏɴ:</b> {channel.get('button_text', 'Default')}\n\n"""
    
    channels_text += f"<b>📊 ᴛᴏᴛᴀʟ:</b> {len(FORCE_CHANNELS)} ᴄʜᴀɴɴᴇʟꜱ"
    
    keyboard = [
        [InlineKeyboardButton("➕ ᴀᴅᴅ ɴᴇᴡ ᴄʜᴀɴɴᴇʟ", callback_data="add_channel_guide")],
        [InlineKeyboardButton("🗑 ʀᴇᴍᴏᴠᴇ ᴄʜᴀɴɴᴇʟ", callback_data="remove_channel")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(channels_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

async def removechannel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a force join channel"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ <b>ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ.</b>", parse_mode=ParseMode.HTML)
        return
    
    if not context.args:
        await update.message.reply_text("ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ᴄʜᴀɴɴᴇʟ ᴜꜱᴇʀɴᴀᴍᴇ.\nᴜꜱᴀɢᴇ: <code>/removechannel ᴜꜱᴇʀɴᴀᴍᴇ</code>", parse_mode=ParseMode.HTML)
        return
    
    username = context.args[0].replace('@', '')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if it's a primary channel (cannot remove)
    cursor.execute('SELECT username FROM channels WHERE username = ?', (username,))
    channel = cursor.fetchone()
    
    if not channel:
        await update.message.reply_text(f"❌ <b>ᴄʜᴀɴɴᴇʟ @{username} ɴᴏᴛ ꜰᴏᴜɴᴅ!</b>", parse_mode=ParseMode.HTML)
        conn.close()
        return
    
    # Check if it's a primary channel
    primary_usernames = [ch['username'] for ch in PRIMARY_CHANNELS]
    if username in primary_usernames:
        await update.message.reply_text(f"❌ <b>ᴄᴀɴɴᴏᴛ ʀᴇᴍᴏᴠᴇ ᴘʀɪᴍᴀʀʏ ᴄʜᴀɴɴᴇʟ @{username}!</b>", parse_mode=ParseMode.HTML)
        conn.close()
        return
    
    # Remove channel
    cursor.execute('DELETE FROM channels WHERE username = ?', (username,))
    conn.commit()
    conn.close()
    
    # Reload force channels cache
    load_force_channels_from_db()
    
    await update.message.reply_text(f"✅ <b>ᴄʜᴀɴɴᴇʟ @{username} ʀᴇᴍᴏᴠᴇᴅ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ!</b>", parse_mode=ParseMode.HTML)

# NEW COMMAND HANDLERS FOR NEW APIS (keeping existing ones, just showing they remain the same)
async def pak_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /pak command for Pakistan number lookup"""
    if not await force_join_check(update, context):
        return
    
    if not context.args:
        await update.message.reply_text(
            "ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ᴘᴀᴋɪꜱᴛᴀɴ ᴘʜᴏɴᴇ ɴᴜᴍʙᴇʀ.\nᴜꜱᴀɢᴇ: <code>/pak 6110129714707</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    phone = context.args[0]
    await pak_command_handler(update, context, phone)

async def pak_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, phone: str):
    """Handle Pakistan number lookup"""
    try:
        response = requests.get(f"{APIS['pak']}{phone}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            await send_api_result(update, context, "pak", phone, data)
        else:
            raise Exception("API Error")
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ <code>ᴇʀʀᴏʀ</code>ᴊᴏɪɴ @zionixportal ꜰᴏʀ ꜰᴜʀᴛʜᴇʀ ᴜᴘᴅᴀᴛᴇꜱ",
            parse_mode=ParseMode.HTML
        )

async def ffinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ffinfo command for Free Fire info"""
    if not await force_join_check(update, context):
        return
    
    if not context.args:
        await update.message.reply_text(
            "ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ꜰʀᴇᴇ ꜰɪʀᴇ ᴜɪᴅ.\nᴜꜱᴀɢᴇ: <code>/ffinfo 2819649271</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    uid = context.args[0]
    await ffinfo_command_handler(update, context, uid)

async def ffinfo_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, uid: str):
    """Handle Free Fire info lookup"""
    try:
        response = requests.get(f"{APIS['ffinfo']}{uid}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            await send_api_result(update, context, "ffinfo", uid, data)
        else:
            raise Exception("API Error")
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ <code>ᴇʀʀᴏʀ</code>ᴊᴏɪɴ @zionixportal ꜰᴏʀ ꜰᴜʀᴛʜᴇʀ ᴜᴘᴅᴀᴛᴇꜱ",
            parse_mode=ParseMode.HTML
        )

async def vnum_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /vnum command for vehicle number owner"""
    if not await force_join_check(update, context):
        return
    
    if not context.args:
        await update.message.reply_text(
            "ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ᴠᴇʜɪᴄʟᴇ ɴᴜᴍʙᴇʀ.\nᴜꜱᴀɢᴇ: <code>/vnum DL1CAB1234</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    vehicle_no = context.args[0]
    await vnum_command_handler(update, context, vehicle_no)

async def vnum_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, vehicle_no: str):
    """Handle vehicle number owner lookup"""
    try:
        response = requests.get(f"{APIS['vnum']}{vehicle_no}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            await send_api_result(update, context, "vnum", vehicle_no, data)
        else:
            raise Exception("API Error")
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ <code>ᴇʀʀᴏʀ</code>ᴊᴏɪɴ @zionixportal ꜰᴏʀ ꜰᴜʀᴛʜᴇʀ ᴜᴘᴅᴀᴛᴇꜱ",
            parse_mode=ParseMode.HTML
        )

async def rto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /rto command for RTO vehicle info"""
    if not await force_join_check(update, context):
        return
    
    if not context.args:
        await update.message.reply_text(
            "ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ᴠᴇʜɪᴄʟᴇ ɴᴜᴍʙᴇʀ.\nᴜꜱᴀɢᴇ: <code>/rto WB52AB9888</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    vehicle_no = context.args[0]
    await rto_command_handler(update, context, vehicle_no)

async def rto_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, vehicle_no: str):
    """Handle RTO vehicle info lookup"""
    try:
        response = requests.get(f"{APIS['rto']}{vehicle_no}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            await send_api_result(update, context, "rto", vehicle_no, data)
        else:
            raise Exception("API Error")
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ <b>ᴇʀʀᴏʀ in api </b>ᴊᴏɪɴ @zionixportal ꜰᴏʀ ꜰᴜʀᴛʜᴇʀ ᴜᴘᴅᴀᴛᴇꜱ",
            parse_mode=ParseMode.HTML
        )

async def leak_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /leak command for leaked data search"""
    if not await force_join_check(update, context):
        return
    
    if not context.args:
        await update.message.reply_text(
            "ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ꜱᴇᴀʀᴄʜ ɪᴅ (ɴᴜᴍʙᴇʀ, ᴀᴀᴅʜᴀʀ, ɴᴀᴍᴇ).\nᴜꜱᴀɢᴇ: <code>/leak modi</code>\nɴᴏᴛᴇ: ɴᴜᴍʙᴇʀ ꜱʜᴏᴜʟᴅ ʙᴇ ɪɴ ɪɴᴛᴇʀɴᴀᴛɪᴏɴᴀʟ ꜰᴏʀᴍᴀᴛ",
            parse_mode=ParseMode.HTML
        )
        return
    
    leak_id = context.args[0]
    await leak_command_handler(update, context, leak_id)

async def leak_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, leak_id: str):
    """Handle leaked data search"""
    try:
        response = requests.get(f"{APIS['leak']}{leak_id}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            await send_api_result(update, context, "leak", leak_id, data)
        else:
            raise Exception("API Error")
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ <code>ᴇʀʀᴏʀ</code>ᴊᴏɪɴ @zionixportal ꜰᴏʀ ꜰᴜʀᴛʜᴇʀ ᴜᴘᴅᴀᴛᴇꜱ",
            parse_mode=ParseMode.HTML
        )

async def imei_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /imei command for IMEI lookup"""
    if not await force_join_check(update, context):
        return
    
    if not context.args:
        await update.message.reply_text(
            "ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ɪᴍᴇɪ ɴᴜᴍʙᴇʀ.\nᴜꜱᴀɢᴇ: <code>/imei 123456789012345</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    imei_no = context.args[0]
    await imei_command_handler(update, context, imei_no)

async def imei_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, imei_no: str):
    """Handle IMEI lookup"""
    try:
        response = requests.get(f"{APIS['imei']}{imei_no}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            await send_api_result(update, context, "imei", imei_no, data)
        else:
            raise Exception("API Error")
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ <code>ᴇʀʀᴏʀ</code>ᴊᴏɪɴ @zionixportal ꜰᴏʀ ꜰᴜʀᴛʜᴇʀ ᴜᴘᴅᴀᴛᴇꜱ",
            parse_mode=ParseMode.HTML
        )

async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ai command for AI chat (UPDATED with new API)"""
    if not await force_join_check(update, context):
        return
    
    if not context.args:
        await update.message.reply_text(
            "ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ʏᴏᴜʀ ǫᴜᴇꜱᴛɪᴏɴ.\nᴜꜱᴀɢᴇ: <code>/ai Hello, how are you?</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    query = " ".join(context.args)
    await ai_command_handler(update, context, query)

async def ai_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """Handle AI chat with new API"""
    try:
        # URL encode the query
        import urllib.parse
        encoded_query = urllib.parse.quote(query)
        url = f"{APIS['ai']}{encoded_query}"
        
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            await send_api_result(update, context, "ai", query, data)
        else:
            raise Exception(f"API Error: {response.status_code}")
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ <code>ᴇʀʀᴏʀ</code>ᴊᴏɪɴ @zionixportal ꜰᴏʀ ꜰᴜʀᴛʜᴇʀ ᴜᴘᴅᴀᴛᴇꜱ",
            parse_mode=ParseMode.HTML
        )

# Callback query handler - Updated with new button handlers
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    chat = update.effective_chat
    
    if query.data.startswith("verify_join_"):
        parts = query.data.split("_")
        if len(parts) >= 4:
            chat_id = int(parts[2])
            user_id = int(parts[3])
            
            if user.id != user_id:
                await query.answer("ᴛʜɪꜱ ʙᴜᴛᴛᴏɴ ɪꜱ ɴᴏᴛ ꜰᴏʀ ʏᴏᴜ!", show_alert=True)
                return
            
            all_joined, not_joined = await check_all_channels(user.id, context)
            
            if not all_joined:
                keyboard = []
                for channel in not_joined:
                    button_text = channel.get('button_text', f"➕ ᴊᴏɪɴ {channel['title']}")
                    keyboard.append([InlineKeyboardButton(button_text, url=channel['invite_link'])])
                
                keyboard.append([InlineKeyboardButton("✅ ɪ'ᴠᴇ ᴊᴏɪɴᴇᴅ", callback_data=f"verify_join_{chat_id}_{user.id}")])
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_caption(
                    caption=f"❌ <b>ᴘʟᴇᴀꜱᴇ ᴊᴏɪɴ ᴀʟʟ ᴄʜᴀɴɴᴇʟꜱ!</b>\n\n👤 <b>ᴜꜱᴇʀ:</b> {user.mention_html()}\n\n<b>ʏᴏᴜ ʜᴀᴠᴇɴ'ᴛ ᴊᴏɪɴᴇᴅ ᴀʟʟ ʀᴇǫᴜɪʀᴇᴅ ᴄʜᴀɴɴᴇʟꜱ.</b>",
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
            else:
                success_text = f"""
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>✅ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟ</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>

👤 <b>ᴜꜱᴇʀ:</b> {user.mention_html()}

<b>ʏᴏᴜ ʜᴀᴠᴇ ᴊᴏɪɴᴇᴅ ᴀʟʟ ʀᴇǫᴜɪʀᴇᴅ ᴄʜᴀɴɴᴇʟꜱ.</b>
<b>ʏᴏᴜ ᴄᴀɴ ɴᴏᴡ ᴜꜱᴇ ᴀʟʟ ʙᴏᴛ ꜰᴇᴀᴛᴜʀᴇꜱ.</b>
"""
                
                try:
                    await query.edit_message_caption(
                        caption=success_text,
                        parse_mode=ParseMode.HTML
                    )
                except:
                    await query.edit_message_text(
                        text=success_text,
                        parse_mode=ParseMode.HTML
                    )
    
    elif query.data == "search_services":
        # ... (existing code remains the same) ...
        pass
    
    elif query.data == "add_channel_guide":
        help_text = """
<b>📝 ᴀᴅᴅ ɴᴇᴡ ꜰᴏʀᴄᴇ ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ</b>

<code>/addchannel username "Channel Title" invite_link [button_text] [is_private]</code>

<b>📌 ᴘᴀʀᴀᴍᴇᴛᴇʀꜱ:</b>
• <code>username</code> - ᴄʜᴀɴɴᴇʟ ᴜꜱᴇʀɴᴀᴍᴇ (ᴡɪᴛʜᴏᴜᴛ @)
• <code>Channel Title</code> - ᴄʜᴀɴɴᴇʟ ɴᴀᴍᴇ (ɪɴ ǫᴜᴏᴛᴇꜱ)
• <code>invite_link</code> - ɪɴᴠɪᴛᴇ ʟɪɴᴋ
• <code>button_text</code> - (ᴏᴘᴛɪᴏɴᴀʟ) ʙᴜᴛᴛᴏɴ ᴛᴇxᴛ
• <code>is_private</code> - (ᴏᴘᴛɪᴏɴᴀʟ) 1 ꜰᴏʀ ᴘʀɪᴠᴀᴛᴇ, 0 ꜰᴏʀ ᴘᴜʙʟɪᴄ (ᴅᴇꜰᴀᴜʟᴛ: 0)

<b>📋 ᴇxᴀᴍᴘʟᴇꜱ:</b>
<code>/addchannel mychannel "ᴍʏ ᴄʜᴀɴɴᴇʟ" https://t.me/mychannel</code>
<code>/addchannel privatechannel "ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀɴɴᴇʟ" https://t.me/privatechannel "➕ ᴊᴏɪɴ ᴘʀɪᴠᴀᴛᴇ" 1</code>
"""
        await query.message.reply_text(help_text, parse_mode=ParseMode.HTML)
    
    elif query.data == "remove_channel":
        if not is_admin(user.id):
            await query.answer("❌ ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ!", show_alert=True)
            return
        
        await query.message.reply_text(
            "ᴜꜱᴇ <code>/removechannel ᴜꜱᴇʀɴᴀᴍᴇ</code> ᴛᴏ ʀᴇᴍᴏᴠᴇ ᴀ ᴄʜᴀɴɴᴇʟ.\n\n"
            "ᴜꜱᴇ <code>/listchannels</code> ᴛᴏ ꜱᴇᴇ ᴀʟʟ ᴀᴠᴀɪʟᴀʙʟᴇ ᴄʜᴀɴɴᴇʟꜱ.",
            parse_mode=ParseMode.HTML
        )
    
    elif query.data == "check_credits":
        # ... (existing code remains the same) ...
        pass
    
    elif query.data == "check_stats":
        # ... (existing code remains the same) ...
        pass
    
    elif query.data == "help":
        await help_command(update, context)
    
    elif query.data == "donate":
        await donate_command(update, context)
    
    elif query.data.startswith("service_"):
        # ... (existing code remains the same) ...
        pass
    
    elif query.data == "back_main":
        # ... (existing code remains the same) ...
        pass

# Message handler for service responses
async def handle_service_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle responses to service queries"""
    user = update.effective_user
    
    if 'waiting_for' in context.user_data and update.message.text:
        service = context.user_data['waiting_for']
        query = update.message.text
        
        # Check force join first
        if not await force_join_check(update, context):
            return
        
        # Handle based on service
        if service == "num":
            await num_command_handler(update, context, query)
        elif service == "aadhar":
            await aadhar_command_handler(update, context, query)
        elif service == "ip":
            await ip_command_handler(update, context, query)
        elif service == "vehicle":
            await vehicle_command_handler(update, context, query)
        elif service == "tg":
            await tg_command_handler(update, context, query)
        elif service == "insta":
            await insta_command_handler(update, context, query)
        elif service == "gst":
            await gst_command_handler(update, context, query)
        elif service == "ifsc":
            await ifsc_command_handler(update, context, query)
        elif service == "ai":
            await ai_command_handler(update, context, query)
        elif service == "img":
            await img_command_handler(update, context, query)
        elif service == "mail":
            await mail_command_handler(update, context, query)
        elif service == "fam":
            await fam_command_handler(update, context, query)
        elif service == "ffuid":
            await ffuid_command_handler(update, context, query)
        elif service == "pak":
            await pak_command_handler(update, context, query)
        elif service == "ffinfo":
            await ffinfo_command_handler(update, context, query)
        elif service == "vnum":
            await vnum_command_handler(update, context, query)
        elif service == "rto":
            await rto_command_handler(update, context, query)
        elif service == "leak":
            await leak_command_handler(update, context, query)
        elif service == "imei":
            await imei_command_handler(update, context, query)
        
        # Clear waiting state
        del context.user_data['waiting_for']

# Existing command handlers (keeping them for backward compatibility)
# ... (all existing command handlers remain the same) ...

# Stats command
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user statistics"""
    user = update.effective_user
    chat = update.effective_chat
    
    # Check force join first
    if not await force_join_check(update, context):
        return
    
    user_stats = get_user_stats(user.id)
    total_users = get_user_count()
    total_groups = get_group_count()
    total_searches_all = get_total_searches()
    
    if user_stats:
        user_searches = user_stats['total_searches'] or 0
        join_date = user_stats['join_date']
        credits = user_stats['credits'] or 0
        referrals = user_stats['referrals'] or 0
        
        # Calculate days since join
        try:
            join_dt = datetime.strptime(join_date, '%Y-%m-%d %H:%M:%S')
            days_active = (datetime.now() - join_dt).days
        except:
            days_active = 0
        
        stats_text = f"""
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>📊 ʙᴏᴛ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>

{('👤 <b>ᴜꜱᴇʀ:</b> ' + user.mention_html() + '\n') if chat.type != "private" else ''}
<b>📈 ᴘᴇʀꜱᴏɴᴀʟ ꜱᴛᴀᴛꜱ:</b>
👤 <b>ᴜꜱᴇʀ:</b> {user.first_name}
🆔 <b>ɪᴅ:</b> <code>{user.id}</code>
📅 <b>ᴊᴏɪɴᴇᴅ:</b> <code>{join_date}</code>
📆 <b>ᴅᴀʏꜱ ᴀᴄᴛɪᴠᴇ:</b> <code>{days_active}</code>
🔍 <b>ʏᴏᴜʀ ꜱᴇᴀʀᴄʜᴇꜱ:</b> <code>{user_searches}</code>
💰 <b>ᴄʀᴇᴅɪᴛꜱ:</b> <code>{credits}</code>
👥 <b>ʀᴇꜰᴇʀʀᴀʟꜱ:</b> <code>{referrals}</code>

<b>🌍 ɢʟᴏʙᴀʟ ꜱᴛᴀᴛꜱ:</b>
👥 <b>ᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ:</b> <code>{total_users}</code>
👥 <b>ᴛᴏᴛᴀʟ ɢʀᴏᴜᴘꜱ:</b> <code>{total_groups}</code>
🔎 <b>ᴛᴏᴛᴀʟ ꜱᴇᴀʀᴄʜᴇꜱ:</b> <code>{total_searches_all}</code>
"""
        
        keyboard = [
            [
                InlineKeyboardButton("🤖 ᴜꜱᴇ ᴍᴇ ʜᴇʀᴇ", url="https://t.me/zionix_chats"),
                InlineKeyboardButton("📨 ᴜꜱᴇ ɪɴ ᴘᴍ", url=f"https://t.me/{context.bot.username}?start")
            ],
            [
                InlineKeyboardButton("➕ ᴀᴅᴅ ᴛᴏ ɢʀᴏᴜᴘ", url=f"https://t.me/{context.bot.username}?startgroup=true"),
                InlineKeyboardButton("💰 ᴄʀᴇᴅɪᴛꜱ", callback_data="check_credits")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            text=stats_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "ᴜꜱᴇʀ ᴅᴀᴛᴀ ɴᴏᴛ ꜰᴏᴜɴᴅ. ᴘʟᴇᴀꜱᴇ ᴜꜱᴇ /ꜱᴛᴀʀᴛ ꜰɪʀꜱᴛ.",
            parse_mode=ParseMode.HTML
        )

# Credits command
async def credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user credits"""
    user = update.effective_user
    chat = update.effective_chat
    
    credits = get_user_credits(user.id, chat.type)
    credits_text = f"""
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>💰 ʏᴏᴜʀ ᴄʀᴇᴅɪᴛꜱ</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>

👤 <b>ᴜꜱᴇʀ:</b> {user.first_name}
🆔 <b>ɪᴅ:</b> <code>{user.id}</code>
💰 <b>ᴀᴠᴀɪʟᴀʙʟᴇ ᴄʀᴇᴅɪᴛꜱ:</b> <code>{credits}</code>
🎁 <b>ᴅᴀɪʟʏ ʙᴏɴᴜꜱ:</b> 5 ᴄʀᴇᴅɪᴛꜱ
🤝 <b>ʀᴇꜰᴇʀʀᴀʟ ʙᴏɴᴜꜱ:</b> 10 ᴄʀᴇᴅɪᴛꜱ
🔗 <b>ʏᴏᴜʀ ʀᴇꜰᴇʀʀᴀʟ ʟɪɴᴋ:</b>
<code>https://t.me/{context.bot.username}?start={user.id}</code>
"""
    
    keyboard = [
        [
            InlineKeyboardButton("🤖 ᴜꜱᴇ ᴍᴇ ʜᴇʀᴇ", url="https://t.me/zionix_chats"),
            InlineKeyboardButton("📨 ᴜꜱᴇ ɪɴ ᴘᴍ", url=f"https://t.me/{context.bot.username}?start")
        ],
        [
            InlineKeyboardButton("➕ ᴀᴅᴅ ᴛᴏ ɢʀᴏᴜᴘ", url=f"https://t.me/{context.bot.username}?startgroup=true"),
            InlineKeyboardButton("📊 ꜱᴛᴀᴛꜱ", callback_data="check_stats")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text=credits_text,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )

# Help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message"""
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type == "private" and not await force_join_check(update, context):
        return
    
    help_text = f"""
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>🆘 ᴢɪᴏɴɪx ᴏꜱɪɴᴛ ʙᴏᴛ ʜᴇʟᴘ</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>

{('👤 <b>ᴜꜱᴇʀ:</b> ' + user.mention_html() + '\n') if chat.type != "private" else ''}
<b>🔍 ᴀᴠᴀɪʟᴀʙʟᴇ ᴄᴏᴍᴍᴀɴᴅꜱ:</b>

<b>📊 ʙᴀꜱɪᴄ ᴄᴏᴍᴍᴀɴᴅꜱ:</b>
• /start - ꜱᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ
• /help - ꜱʜᴏᴡ ᴛʜɪꜱ ʜᴇʟᴘ
• /stats - ᴠɪᴇᴡ ʏᴏᴜʀ ꜱᴛᴀᴛꜱ
• /credits - ᴄʜᴇᴄᴋ ʏᴏᴜʀ ᴄʀᴇᴅɪᴛꜱ
• /donate - ꜱᴜᴘᴘᴏʀᴛ ᴛʜᴇ ʙᴏᴛ

<b>🔎 ᴏꜱɪɴᴛ ꜱᴇʀᴠɪᴄᴇꜱ:</b>
• /num [ᴘʜᴏɴᴇ] - ᴍᴏʙɪʟᴇ ɴᴜᴍʙᴇʀ ʟᴏᴏᴋᴜᴘ
• /aadhar [ɪᴅ] - ᴀᴀᴅʜᴀʀ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ
• /ip [ᴀᴅᴅʀᴇꜱꜱ] - ɪᴘ ɪɴꜰᴏʀᴍᴀᴛɪᴏɴ
• /vehicle [ʀᴇɢ] - ᴠᴇʜɪᴄʟᴇ ᴅᴇᴛᴀɪʟꜱ
• /tg [ᴜꜱᴇʀ] - ᴛᴇʟᴇɢʀᴀᴍ ᴜꜱᴇʀ ɪɴꜰᴏ
• /insta [ᴜꜱᴇʀ] - ɪɴꜱᴛᴀɢʀᴀᴍ ᴘʀᴏꜰɪʟᴇ
• /gst [ɴᴜᴍʙᴇʀ] - ɢꜱᴛ ᴅᴇᴛᴀɪʟꜱ
• /ifsc [ᴄᴏᴅᴇ] - ɪꜰꜱᴄ ʟᴏᴏᴋᴜᴘ
• /ai [ǫᴜᴇʀʏ] - ᴀɪ ᴀꜱꜱɪꜱᴛᴀɴᴛ
• /img [ǫᴜᴇʀʏ] - ɪᴍᴀɢᴇ ꜱᴇᴀʀᴄʜ
• /mail [ᴇᴍᴀɪʟ] - ᴇᴍᴀɪʟ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ
• /fam [ɪᴅ] - ꜰᴀᴍɪʟʏ ᴅᴇᴛᴀɪʟꜱ
• /ffuid [ᴜɪᴅ] - ꜰʀᴇᴇ ꜰɪʀᴇ ᴜꜱᴇʀ ɪᴅ
• /pak [ɴᴜᴍʙᴇʀ] - ᴘᴀᴋɪꜱᴛᴀɴ ɴᴜᴍʙᴇʀ ʟᴏᴏᴋᴜᴘ
• /ffinfo [ᴜɪᴅ] - ꜰʀᴇᴇ ꜰɪʀᴇ ɪɴꜰᴏ
• /vnum [ᴠᴇʜɪᴄʟᴇ] - ᴠᴇʜɪᴄʟᴇ ᴏᴡɴᴇʀ
• /rto [ᴠᴇʜɪᴄʟᴇ] - ʀᴛᴏ ᴠᴇʜɪᴄʟᴇ ɪɴꜰᴏ
• /leak [ɪᴅ] - ʟᴇᴀᴋᴇᴅ ᴅᴀᴛᴀ ꜱᴇᴀʀᴄʜ
• /imei [ɴᴜᴍʙᴇʀ] - ɪᴍᴇɪ ɴᴜᴍʙᴇʀ ʟᴏᴏᴋᴜᴘ

<b>👑 ᴀᴅᴍɪɴ ᴄᴏᴍᴍᴀɴᴅꜱ:</b>
• /broadcast [ᴍꜱɢ] - ʙʀᴏᴀᴅᴄᴀꜱᴛ ᴍᴇꜱꜱᴀɢᴇ
• /ban [ᴜꜱᴇʀ_ɪᴅ] - ʙᴀɴ ᴜꜱᴇʀ
• /unban [ᴜꜱᴇʀ_ɪᴅ] - ᴜɴʙᴀɴ ᴜꜱᴇʀ
• /addadmin [ᴜꜱᴇʀ_ɪᴇᴅ] - ᴀᴅᴅ ꜱᴜʙ-ᴀᴅᴍɪɴ
• /addchannel - ᴀᴅᴅ ɴᴇᴡ ꜰᴏʀᴄᴇ ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ
• /listchannels - ʟɪꜱᴛ ᴀʟʟ ꜰᴏʀᴄᴇ ᴄʜᴀɴɴᴇʟꜱ
• /removechannel - ʀᴇᴍᴏᴠᴇ ꜰᴏʀᴄᴇ ᴄʜᴀɴɴᴇʟ
• /getdb - ɢᴇᴛ ᴅᴀᴛᴀʙᴀꜱᴇ ꜰɪʟᴇ

<b>💰 ᴄʀᴇᴅɪᴛ ꜱʏꜱᴛᴇᴍ:</b>
• 🎁 5 ᴅᴀɪʟʏ ᴄʀᴇᴅɪᴛꜱ ꜰᴏʀ ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀᴛ
• 🤝 10 ᴄʀᴇᴅɪᴛꜱ ᴘᴇʀ ʀᴇꜰᴇʀʀᴀʟ
• 👥 ᴜɴʟɪᴍɪᴛᴇᴅ ᴄʀᴇᴅɪᴛꜱ ɪɴ ɢʀᴏᴜᴘꜱ
• 🔗 ʀᴇꜰᴇʀʀᴀʟ ʟɪɴᴋ: https://t.me/{context.bot.username}?start={user.id}

<b>⚠️ ɴᴏᴛᴇ:</b> ꜱᴏᴍᴇ ꜱᴇʀᴠɪᴄᴇꜱ ᴍᴀʏ ʜᴀᴠᴇ ᴀᴘɪ ʟɪᴍɪᴛꜱ.
<b>👥 ᴍɪɴɪᴍᴜᴍ ɢʀᴏᴜᴘ ꜱɪᴢᴇ:</b> {MIN_GROUP_MEMBERS} ᴍᴇᴍʙᴇʀꜱ ʀᴇǫᴜɪʀᴇᴅ
<b>📢 ꜰᴏʀᴄᴇ ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟꜱ:</b> {', '.join([f'@{ch["username"]}' for ch in FORCE_CHANNELS[:3]])}
"""
    
    keyboard = [
        [
            InlineKeyboardButton("🤖 ᴜꜱᴇ ᴍᴇ ʜᴇʀᴇ", url="https://t.me/zionix_chats"),
            InlineKeyboardButton("📨 ᴜꜱᴇ ɪɴ ᴘᴍ", url=f"https://t.me/{context.bot.username}?start")
        ],
        [
            InlineKeyboardButton("➕ ᴀᴅᴅ ᴛᴏ ɢʀᴏᴜᴘ", url=f"https://t.me/{context.bot.username}?startgroup=true"),
            InlineKeyboardButton("💰 ᴄʀᴇᴅɪᴛꜱ", callback_data="check_credits")
        ],
        [
            InlineKeyboardButton("📊 ꜱᴛᴀᴛꜱ", callback_data="check_stats"),
            InlineKeyboardButton("💝 ᴅᴏɴᴀᴛᴇ", callback_data="donate")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        if chat.type == "private":
            await update.message.reply_photo(
                photo="https://t.me/imgsrcvvv/2",
                caption=help_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                text=help_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Error in help command: {e}")
        await update.message.reply_text(
            text=help_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )

# Admin commands
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast message to all users"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ <b>ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ.</b>", parse_mode=ParseMode.HTML)
        return
    
    if not context.args:
        await update.message.reply_text(
            "ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴍᴇꜱꜱᴀɢᴇ ᴛᴏ ʙʀᴏᴀᴅᴄᴀꜱᴛ.\nᴜꜱᴀɢᴇ: <code>/broadcast ʜᴇʟʟᴏ ᴜꜱᴇʀꜱ!</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    message = " ".join(context.args)
    broadcast_text = f"""
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>📢 ʙʀᴏᴀᴅᴄᴀꜱᴛ ᴍᴇꜱꜱᴀɢᴇ</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>

{message}
"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE is_banned = 0')
    users = cursor.fetchall()
    conn.close()
    
    total_users = len(users)
    success_count = 0
    fail_count = 0
    
    status_msg = await update.message.reply_text(f"📤 <b>ʙʀᴏᴀᴅᴄᴀꜱᴛɪɴɢ ᴛᴏ {total_users} ᴜꜱᴇʀꜱ...</b>", parse_mode=ParseMode.HTML)
    
    for user_row in users:
        try:
            await context.bot.send_message(
                chat_id=user_row['user_id'],
                text=broadcast_text,
                parse_mode=ParseMode.HTML
            )
            success_count += 1
        except Exception as e:
            fail_count += 1
        
        await asyncio.sleep(0.1)
    
    await status_msg.edit_text(
        f"✅ <b>ʙʀᴏᴀᴅᴄᴀꜱᴛ ᴄᴏᴍᴘʟᴇᴛᴇᴅ!</b>\n\n"
        f"📊 <b>ꜱᴛᴀᴛꜱ:</b>\n"
        f"• ᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ: <code>{total_users}</code>\n"
        f"• ꜱᴜᴄᴄᴇꜱꜱ: <code>{success_count}</code>\n"
        f"• ꜰᴀɪʟᴇᴅ: <code>{fail_count}</code>",
        parse_mode=ParseMode.HTML
    )

async def getdb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send database file to owner"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ <b>ᴏɴʟʏ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜꜱᴇ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ.</b>", parse_mode=ParseMode.HTML)
        return
    
    # Check if database file exists
    if not os.path.exists('users.db'):
        await update.message.reply_text("ᴅᴀᴛᴀʙᴀꜱᴇ ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ.")
        return
    
    try:
        # Send database file
        with open('users.db', 'rb') as db_file:
            await update.message.reply_document(
                document=db_file,
                filename='users.db',
                caption="<b>📊 ᴅᴀᴛᴀʙᴀꜱᴇ ꜰɪʟᴇ</b>\n\nʜᴇʀᴇ ɪꜱ ᴛʜᴇ ᴜꜱᴇʀꜱ ᴅᴀᴛᴀʙᴀꜱᴇ ꜰɪʟᴇ."
            )
    except Exception as e:
        await update.message.reply_text(f"ᴇʀʀᴏʀ ꜱᴇɴᴅɪɴɢ ᴅᴀᴛᴀʙᴀꜱᴇ: {str(e)}")

async def addadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add new admin"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ <b>ᴏɴʟʏ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜꜱᴇ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ.</b>", parse_mode=ParseMode.HTML)
        return
    
    if not context.args:
        await update.message.reply_text(
            "ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ᴜꜱᴇʀ ɪᴅ.\nᴜꜱᴀɢᴇ: <code>/addadmin ᴜꜱᴇʀ_ɪᴅ</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        new_admin_id = int(context.args[0])
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO admins (user_id, added_by) VALUES (?, ?)', (new_admin_id, user_id))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            f"✅ <b>ᴜꜱᴇʀ {new_admin_id} ʜᴀꜱ ʙᴇᴇɴ ᴀᴅᴅᴇᴅ ᴀꜱ ᴀɴ ᴀᴅᴍɪɴ.</b>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ <b>ᴇʀʀᴏʀ:</b> {str(e)}",
            parse_mode=ParseMode.HTML
        )

# Database backup job
async def backup_database(context: ContextTypes.DEFAULT_TYPE):
    """Send database backup to log channel"""
    try:
        if os.path.exists('users.db'):
            with open('users.db', 'rb') as db_file:
                await context.bot.send_document(
                    chat_id=LOG_CHANNEL_REGISTRATION,
                    document=db_file,
                    filename=f"users_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                    caption="<b>📊 ᴅᴀᴛᴀʙᴀꜱᴇ ʙᴀᴄᴋᴜᴘ</b>\n\nᴀᴜᴛᴏᴍᴀᴛɪᴄ ʙᴀᴄᴋᴜᴘ ᴇᴠᴇʀʏ 12 ʜᴏᴜʀꜱ."
                )
        logger.info("✅ Database backup sent to log channel")
    except Exception as e:
        logger.error(f"Failed to backup database: {e}")
        await send_log_to_channel(context, f"❌ <b>ꜰᴀɪʟᴇᴅ ᴛᴏ ʙᴀᴄᴋᴜᴘ ᴅᴀᴛᴀʙᴀꜱᴇ:</b> {str(e)}", "error")

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    
    # Send error to error log channel
    error_msg = f"""
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>❌ ʙᴏᴛ ᴇʀʀᴏʀ</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>

<b>📅 ᴛɪᴍᴇ:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>
<b>🔄 ᴜᴘᴅᴀᴛᴇ:</b> <code>{update}</code>
<b>⚠️ ᴇʀʀᴏʀ:</b> <code>{context.error}</code>
"""
    
    await send_log_to_channel(context, error_msg, "error")
    
    # Send error message to user
    if update and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ <b>ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ. ᴘʟᴇᴀꜱᴇ ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ.</b>",
                parse_mode=ParseMode.HTML
            )
        except:
            pass

async def post_init(application: Application):
    """Set bot commands after initialization"""
    commands = [
        BotCommand("start", "ꜱᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ"),
        BotCommand("help", "ꜱʜᴏᴡ ʜᴇʟᴘ"),
        BotCommand("num", "ᴍᴏʙɪʟᴇ ɴᴜᴍʙᴇʀ ʟᴏᴏᴋᴜᴘ"),
        BotCommand("aadhar", "ᴀᴀᴅʜᴀʀ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ"),
        BotCommand("ip", "ɪᴘ ɪɴꜰᴏʀᴍᴀᴛɪᴏɴ"),
        BotCommand("vehicle", "ᴠᴇʜɪᴄʟᴇ ᴅᴇᴛᴀɪʟꜱ"),
        BotCommand("tg", "ᴛᴇʟᴇɢʀᴀᴍ ᴜꜱᴇʀ ɪɴꜰᴏ"),
        BotCommand("insta", "ɪɴꜱᴛᴀɢʀᴀᴍ ᴘʀᴏꜰɪʟᴇ"),
        BotCommand("gst", "ɢꜱᴛ ᴅᴇᴛᴀɪʟꜱ"),
        BotCommand("ifsc", "ɪꜰꜱᴄ ʟᴏᴏᴋᴜᴘ"),
        BotCommand("ai", "ᴀɪ ᴀꜱꜱɪꜱᴛᴀɴᴛ"),
        BotCommand("img", "ɪᴍᴀɢᴇ ꜱᴇᴀʀᴄʜ"),
        BotCommand("mail", "ᴇᴍᴀɪʟ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ"),
        BotCommand("fam", "ꜰᴀᴍɪʟʏ ᴅᴇᴛᴀɪʟꜱ"),
        BotCommand("ffuid", "ꜰʀᴇᴇ ꜰɪʀᴇ ᴜꜱᴇʀ ɪᴅ"),
        BotCommand("pak", "ᴘᴀᴋɪꜱᴛᴀɴ ɴᴜᴍʙᴇʀ ʟᴏᴏᴋᴜᴘ"),
        BotCommand("ffinfo", "ꜰʀᴇᴇ ꜰɪʀᴇ ɪɴꜰᴏ"),
        BotCommand("vnum", "ᴠᴇʜɪᴄʟᴇ ɴᴜᴍʙᴇʀ ᴏᴡɴᴇʀ"),
        BotCommand("rto", "ʀᴛᴏ ᴠᴇʜɪᴄʟᴇ ɪɴꜰᴏ"),
        BotCommand("leak", "ʟᴇᴀᴋᴇᴅ ᴅᴀᴛᴀ ꜱᴇᴀʀᴄʜ"),
        BotCommand("imei", "ɪᴍᴇɪ ɴᴜᴍʙᴇʀ ʟᴏᴏᴋᴜᴘ"),
        BotCommand("stats", "ᴠɪᴇᴡ ʏᴏᴜʀ ꜱᴛᴀᴛꜱ"),
        BotCommand("credits", "ᴄʜᴇᴄᴋ ʏᴏᴜʀ ᴄʀᴇᴅɪᴛꜱ"),
        BotCommand("donate", "ꜱᴜᴘᴘᴏʀᴛ ᴛʜᴇ ʙᴏᴛ")
    ]
    
    # Admin commands (only visible to admins, but we add them anyway)
    admin_commands = [
        BotCommand("broadcast", "ʙʀᴏᴀᴅᴄᴀꜱᴛ ᴍᴇꜱꜱᴀɢᴇ"),
        BotCommand("addchannel", "ᴀᴅᴅ ɴᴇᴡ ꜰᴏʀᴄᴇ ᴄʜᴀɴɴᴇʟ"),
        BotCommand("listchannels", "ʟɪꜱᴛ ᴀʟʟ ꜰᴏʀᴄᴇ ᴄʜᴀɴɴᴇʟꜱ"),
        BotCommand("removechannel", "ʀᴇᴍᴏᴠᴇ ꜰᴏʀᴄᴇ ᴄʜᴀɴɴᴇʟ"),
        BotCommand("addadmin", "ᴀᴅᴅ ꜱᴜʙ-ᴀᴅᴍɪɴ"),
        BotCommand("getdb", "ɢᴇᴛ ᴅᴀᴛᴀʙᴀꜱᴇ ꜰɪʟᴇ")
    ]
    
    all_commands = commands + admin_commands
    
    try:
        await application.bot.set_my_commands(commands)
        logger.info("✅ Bot commands set successfully")
        
        # Schedule periodic jobs
        application.job_queue.run_repeating(backup_database, interval=43200, first=10)  # 12 hours
        
        # Send startup message
        startup_msg = f"""
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>🚀 ʙᴏᴛ ꜱᴛᴀʀᴛᴇᴅ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ!</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>

⏰ <b>ꜱᴛᴀʀᴛ ᴛɪᴍᴇ:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>
👤 <b>ᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ:</b> <code>{get_user_count()}</code>
👥 <b>ᴛᴏᴛᴀʟ ɢʀᴏᴜᴘꜱ:</b> <code>{get_group_count()}</code>
📢 <b>ꜰᴏʀᴄᴇ ᴄʜᴀɴɴᴇʟꜱ:</b> <code>{len(FORCE_CHANNELS)}</code>
🤖 <b>ʙᴏᴛ:</b> @{application.bot.username}
👑 <b>ᴏᴡɴᴇʀ:</b> <code>{OWNER_ID}</code>

<b>✅ ʀᴇᴀᴅʏ ᴛᴏ ꜱᴇʀᴠᴇ!</b>
"""
        
        await application.bot.send_message(
            chat_id=LOG_CHANNEL_REGISTRATION,
            text=startup_msg,
            parse_mode=ParseMode.HTML
        )
        logger.info("✅ Startup message sent to log channel")
        
    except Exception as e:
        logger.error(f"Failed in post_init: {e}")

# Main function
def main():
    """Start the bot"""
    try:
        application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
        
        # Command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("donate", donate_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("credits", credits_command))
        
        # OSINT commands
        application.add_handler(CommandHandler("num", num_command))
        application.add_handler(CommandHandler("aadhar", aadhar_command))
        application.add_handler(CommandHandler("ip", ip_command))
        application.add_handler(CommandHandler("vehicle", vehicle_command))
        application.add_handler(CommandHandler("tg", tg_command))
        application.add_handler(CommandHandler("insta", insta_command))
        application.add_handler(CommandHandler("gst", gst_command))
        application.add_handler(CommandHandler("ifsc", ifsc_command))
        application.add_handler(CommandHandler("ai", ai_command))
        application.add_handler(CommandHandler("img", img_command))
        application.add_handler(CommandHandler("mail", mail_command))
        application.add_handler(CommandHandler("fam", fam_command))
        application.add_handler(CommandHandler("ffuid", ffuid_command))
        
        # NEW API commands
        application.add_handler(CommandHandler("pak", pak_command))
        application.add_handler(CommandHandler("ffinfo", ffinfo_command))
        application.add_handler(CommandHandler("vnum", vnum_command))
        application.add_handler(CommandHandler("rto", rto_command))
        application.add_handler(CommandHandler("leak", leak_command))
        application.add_handler(CommandHandler("imei", imei_command))
        
        # Admin commands
        application.add_handler(CommandHandler("broadcast", broadcast_command))
        application.add_handler(CommandHandler("getdb", getdb_command))
        application.add_handler(CommandHandler("addchannel", addchannel_command))
        application.add_handler(CommandHandler("listchannels", listchannels_command))
        application.add_handler(CommandHandler("removechannel", removechannel_command))
        application.add_handler(CommandHandler("addadmin", addadmin_command))
        
        # Callback and message handlers
        application.add_handler(CallbackQueryHandler(button_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_service_response))
        
        # Error handler
        application.add_error_handler(error_handler)
        
        # Start bot
        print("=" * 50)
        print(f"🤖 Bot: @{BOT_USERNAME.replace('@', '')}")
        print(f"👑 Owner ID: {OWNER_ID}")
        print(f"📊 Registration Log: {LOG_CHANNEL_REGISTRATION}")
        print(f"🔍 Search Log: {LOG_CHANNEL_SEARCH}")
        print(f"❌ Error Log: {LOG_CHANNEL_ERROR}")
        print(f"👥 Min Group Members: {MIN_GROUP_MEMBERS}")
        print(f"📢 Force Join Channels: {len(FORCE_CHANNELS)} channels loaded")
        print("=" * 50)
        print("🚀 Starting bot...")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()