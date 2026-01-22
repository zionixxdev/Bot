#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

# Primary force join channels (UPDATED: 2x2 layout with 4 channels)
FORCE_CHANNELS = [
    {"title": "ᴢɪᴏɴɪx ᴘᴏʀᴛᴀʟ", "username": "zionixportal", "invite_link": "https://t.me/zionixportal", "is_private": False},
    {"title": "ᴢɪᴏɴɪx ᴘᴏʀᴛᴀʟ 𝟸", "username": "zionix_portal", "invite_link": "https://t.me/zionix_portal", "is_private": False},
    {"title": "ᴇɴᴄᴏʀᴇx ᴏꜱɪɴᴛ", "username": "encorexosint", "invite_link": "https://t.me/encorexosint", "is_private": False},
    {"title": "ᴢɪᴏɴɪx ᴘʏ", "username": "zionixpy", "invite_link": "https://t.me/zionixpy", "is_private": False}
]

# API endpoints (UPDATED: Removed AI, IMG, FAM APIs)
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
    "ffuid": "https://anku-ffapi-inky.vercel.app/ff?uid=",
    
    # NEW APIs from your request
    "pak": "https://pak-info-api.vercel.app/api/lookup?query=",
    "ffinfo": "https://anku-ffapi-inky.vercel.app/ff?uid=",
    "vnum": "https://7.toxictanji0503.workers.dev/vnumowner?vehicle=",
    "rto": "https://api.globalcomputers.shop/?vehicle_number=",
    "leak": "https://aluuxidk.vercel.app/leak?key=6442851093:7ocdcXMi&id=",
    "imei": "https://imei-info.gauravyt566.workers.dev/?imei=",
}

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
    
    # Create groups table with welcome_enabled column
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS groups (
        group_id INTEGER PRIMARY KEY,
        group_name TEXT,
        added_by INTEGER,
        add_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT 1,
        member_count INTEGER DEFAULT 0,
        last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        welcome_enabled BOOLEAN DEFAULT 1,
        welcome_message TEXT DEFAULT '👋 Welcome {first_name} to {group_name}!',
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
        channel_id INTEGER PRIMARY KEY,
        channel_name TEXT,
        username TEXT,
        invite_link TEXT,
        is_private BOOLEAN,
        button_text TEXT,
        added_by INTEGER,
        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Insert primary force channels
    for channel in FORCE_CHANNELS:
        cursor.execute('''
        INSERT OR IGNORE INTO channels (channel_name, username, invite_link, is_private, added_by)
        VALUES (?, ?, ?, ?, ?)
        ''', (channel['title'], channel['username'], channel['invite_link'], 
              channel.get('is_private', False), OWNER_ID))
    
    # Insert owner as admin
    cursor.execute('INSERT OR IGNORE INTO admins (user_id, username, added_by) VALUES (?, ?, ?)', 
                  (OWNER_ID, 'owner', OWNER_ID))
    
    conn.commit()
    conn.close()
    logger.info("✅ Database initialized successfully")

# Initialize database
init_database()

# Database helper functions
def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    return conn

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
        INSERT INTO groups (group_id, group_name, added_by, add_date, is_active, member_count, last_checked, welcome_enabled)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, 1, ?, CURRENT_TIMESTAMP, 1)
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

def get_group_welcome_status(group_id: int) -> bool:
    """Get welcome message status for group"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT welcome_enabled FROM groups WHERE group_id = ?', (group_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return bool(result['welcome_enabled'])
    return True  # Default to enabled

def set_group_welcome_status(group_id: int, status: bool):
    """Set welcome message status for group"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE groups SET welcome_enabled = ? WHERE group_id = ?', (1 if status else 0, group_id))
    conn.commit()
    conn.close()

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
        if channel_info.get('is_private'):
            username = channel_info.get('username')
            if username:
                try:
                    chat_member = await context.bot.get_chat_member(f"@{username}", user_id)
                    return chat_member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
                except:
                    return False
            return False
        else:
            username = channel_info.get('username')
            if username:
                chat_member = await context.bot.get_chat_member(f"@{username}", user_id)
                return chat_member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
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
        
        # Create 2x2 grid of buttons for force join
        keyboard = []
        for i in range(0, len(not_joined), 2):
            row = []
            for j in range(2):
                if i + j < len(not_joined):
                    channel = not_joined[i + j]
                    button_text = f"➕ {channel['title']}"
                    row.append(InlineKeyboardButton(button_text, url=channel['invite_link']))
            if row:
                keyboard.append(row)
        
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

def truncate_json_result(data: dict, max_length: int = 1500) -> Tuple[str, bool]:
    """Truncate JSON result if too long, returns (text, is_truncated)"""
    try:
        formatted = json.dumps(data, indent=2, ensure_ascii=False)
        if len(formatted) <= max_length:
            return f"```json\n{formatted}\n```", False
        
        # Truncate and add truncation notice
        truncated = formatted[:max_length] + "\n... [TRUNCATED - DATA TOO LONG] ...\n"
        truncated += f"\n📁 Full results available as JSON file (Total length: {len(formatted)} characters)"
        return f"```json\n{truncated}\n```", True
    except Exception as e:
        return f"```\n{str(data)[:max_length]}\n```", True

async def send_api_result(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                         service: str, query: str, result: dict):
    """Send formatted API result with truncation if too long"""
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
        "mail": "📧 ᴇᴍᴀɪʟ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ",
        "ffuid": "🎮 ꜰʀᴇᴇ ꜰɪʀᴇ ᴜꜱᴇʀ ɪᴅ",
        "pak": "🇵🇰 ᴘᴀᴋɪꜱᴛᴀɴ ɴᴜᴍʙᴇʀ ʟᴏᴏᴋᴜᴘ",
        "ffinfo": "🎮 ꜰʀᴇᴇ ꜰɪʀᴇ ɪɴꜰᴏ",
        "vnum": "🚗 ᴠᴇʜɪᴄʟᴇ ɴᴜᴍʙᴇʀ ᴏᴡɴᴇʀ",
        "rto": "🏢 ʀᴛᴏ ᴠᴇʜɪᴄʟᴇ ɪɴꜰᴏ",
        "leak": "🔓 ʟᴇᴀᴋᴇᴅ ᴅᴀᴛᴀ ꜱᴇᴀʀᴄʜ",
        "imei": "📱 ɪᴍᴇɪ ɴᴜᴍʙᴇʀ ʟᴏᴏᴋᴜᴘ"
    }
    
    # Format result with truncation if needed
    result_text, is_truncated = truncate_json_result(result)
    
    message_text = f"""
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>{service_titles.get(service, 'ꜱᴇᴀʀᴄʜ ʀᴇꜱᴜʟᴛꜱ')}</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>

{result_text}

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
            # Send photo with result in private chat
            photo_url = "https://t.me/imgsrcvvv/2"
            await update.message.reply_photo(
                photo=photo_url,
                caption=message_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        else:
            # Send only text in groups
            await update.message.reply_text(
                text=message_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        
        # If result was truncated, send full JSON as file
        if is_truncated:
            # Create JSON file
            json_str = json.dumps(result, indent=2, ensure_ascii=False)
            json_file = io.BytesIO(json_str.encode('utf-8'))
            json_file.name = f"{service}_{query}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            await update.message.reply_document(
                document=json_file,
                caption=f"📁 <b>Full JSON results for {query}</b>\n\nService: {service}\nRequested by: {user.mention_html()}",
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
            # Send video with join buttons (2x2 layout)
            keyboard = []
            for i in range(0, len(not_joined), 2):
                row = []
                for j in range(2):
                    if i + j < len(not_joined):
                        channel = not_joined[i + j]
                        button_text = f"➕ {channel['title']}"
                        row.append(InlineKeyboardButton(button_text, url=channel['invite_link']))
                if row:
                    keyboard.append(row)
            
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
• 📧 ᴇᴍᴀɪʟ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ
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
<b>👋 ᴡᴇʟᴄᴏᴍᴇ ᴍᴇꜱꜱᴀɢᴇꜱ:</b> <code>Enabled</code>
"""
            await send_log_to_channel(context, group_log, "registration")
        
        # Group welcome message with inline buttons
        group_welcome = f"""
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>🪬 ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴢɪᴏɴɪx ᴏꜱɪɴᴛ ʙᴏᴛ</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>

<b>👤 ʀᴇǫᴜᴇꜱᴛᴇᴅ ʙʏ:</b> {user.mention_html()}

<b>🌟 ꜰᴇᴀᴛᴜʀᴇꜱ:</b>
• 📱 ᴘʜᴏɴᴇ ɴᴜᴍʙᴇʀ ʟᴏᴏᴋᴜᴘ
• 🆔 ᴀᴀᴅʜᴀʀ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ
• 🌐 ɪᴘ ɪɴꜰᴏʀᴍᴀᴛɪᴏɴ
• 🚗 ᴠᴇʜɪᴄʟᴇ ᴅᴇᴛᴀɪʟꜱ
• 📱 ᴛᴇʟᴇɢʀᴀᴍ ᴜꜱᴇʀ ɪɴꜰᴏ
• 📸 ɪɴꜱᴛᴀɢʀᴀᴍ ᴘʀᴏꜰɪʟᴇ
• 🏢 ɢꜱᴛ ᴅᴇᴛᴀɪʟꜱ
• 🏦 ɪꜰꜱᴄ ᴄᴏᴅᴇ ʟᴏᴏᴋᴜᴘ
• 📧 ᴇᴍᴀɪʟ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ
• 🎮 ꜰʀᴇᴇ ꜰɪʀᴇ ᴜꜱᴇʀ ɪᴅ
• 🇵🇰 ᴘᴀᴋɪꜱᴛᴀɴ ɴᴜᴍʙᴇʀ
• 🎮 ꜰʀᴇᴇ ꜰɪʀᴇ ɪɴꜰᴏ
• 🚗 ᴠᴇʜɪᴄʟᴇ ᴏᴡɴᴇʀ
• 🏢 ʀᴛᴏ ᴠᴇʜɪᴄʟᴇ
• 🔓 ʟᴇᴀᴋᴇᴅ ᴅᴀᴛᴀ
• 📱 ɪᴍᴇɪ ɴᴜᴍʙᴇʀ

<b>👥 ᴜɴʟɪᴍɪᴛᴇᴅ ᴄʀᴇᴅɪᴛꜱ ɪɴ ɢʀᴏᴜᴘꜱ</b>
<b>👋 ᴡᴇʟᴄᴏᴍᴇ ᴍᴇꜱꜱᴀɢᴇꜱ: Enabled</b>
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

# NEW COMMAND HANDLERS FOR NEW APIS
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

# WELCOME COMMAND FOR GROUPS
async def welcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /welcome command for groups to toggle welcome messages"""
    chat = update.effective_chat
    user = update.effective_user
    
    # Check if in group
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text(
            "⚠️ <b>ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ɪꜱ ᴏɴʟʏ ꜰᴏʀ ɢʀᴏᴜᴘꜱ.</b>",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Check if user is group admin or bot admin
    is_group_admin = False
    try:
        chat_member = await context.bot.get_chat_member(chat.id, user.id)
        is_group_admin = chat_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except:
        pass
    
    if not (is_group_admin or is_admin(user.id)):
        await update.message.reply_text(
            "❌ <b>ʏᴏᴜ ᴍᴜꜱᴛ ʙᴇ ᴀɴ ᴀᴅᴍɪɴ ᴛᴏ ᴜꜱᴇ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ.</b>",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Get current status
    current_status = get_group_welcome_status(chat.id)
    
    if context.args:
        arg = context.args[0].lower()
        if arg in ["on", "enable", "yes", "true", "1"]:
            new_status = True
            status_text = "ᴇɴᴀʙʟᴇᴅ ✅"
        elif arg in ["off", "disable", "no", "false", "0"]:
            new_status = False
            status_text = "ᴅɪꜱᴀʙʟᴇᴅ ❌"
        else:
            await update.message.reply_text(
                "⚠️ <b>ᴜꜱᴀɢᴇ:</b> <code>/welcome on</code> <b>ᴏʀ</b> <code>/welcome off</code>",
                parse_mode=ParseMode.HTML
            )
            return
        
        set_group_welcome_status(chat.id, new_status)
        action = "ᴇɴᴀʙʟᴇᴅ" if new_status else "ᴅɪꜱᴀʙʟᴇᴅ"
        
        await update.message.reply_text(
            f"✅ <b>ɢʀᴏᴜᴘ ᴡᴇʟᴄᴏᴍᴇ ᴍᴇꜱꜱᴀɢᴇꜱ {action}.</b>\n\n"
            f"<b>👥 ɢʀᴏᴜᴘ:</b> {chat.title}\n"
            f"<b>👤 ᴄʜᴀɴɢᴇᴅ ʙʏ:</b> {user.mention_html()}\n"
            f"<b>📊 ꜱᴛᴀᴛᴜꜱ:</b> {status_text}",
            parse_mode=ParseMode.HTML
        )
    else:
        # Show current status
        status_text = "ᴇɴᴀʙʟᴇᴅ ✅" if current_status else "ᴅɪꜱᴀʙʟᴇᴅ ❌"
        
        keyboard = [
            [
                InlineKeyboardButton("✅ ᴇɴᴀʙʟᴇ", callback_data=f"welcome_toggle_{chat.id}_on"),
                InlineKeyboardButton("❌ ᴅɪꜱᴀʙʟᴇ", callback_data=f"welcome_toggle_{chat.id}_off")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"<b>👋 ᴡᴇʟᴄᴏᴍᴇ ᴍᴇꜱꜱᴀɢᴇ ꜱᴇᴛᴛɪɴɢꜱ</b>\n\n"
            f"<b>👥 ɢʀᴏᴜᴘ:</b> {chat.title}\n"
            f"<b>📊 ᴄᴜʀʀᴇɴᴛ ꜱᴛᴀᴛᴜꜱ:</b> {status_text}\n\n"
            f"<b>ᴜꜱᴇ ᴛʜᴇ ʙᴜᴛᴛᴏɴꜱ ʙᴇʟᴏᴡ ᴛᴏ ᴛᴏɢɢʟᴇ:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )

# Handle new chat members for welcome messages
async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new group members and send welcome message"""
    if update.message and update.message.new_chat_members:
        chat = update.effective_chat
        
        # Check if welcome messages are enabled for this group
        if not get_group_welcome_status(chat.id):
            return
        
        for new_member in update.message.new_chat_members:
            # Don't welcome bots
            if new_member.is_bot:
                continue
            
            # Welcome message with photo
            welcome_photo = "https://t.me/imgsrcvvv/2"  # Default welcome photo
            welcome_video = "https://t.me/imgsrcvvv/3"  # Alternative welcome video
            
            welcome_text = f"""
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>👋 ᴡᴇʟᴄᴏᴍᴇ {new_member.first_name}!</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>

<b>ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ {chat.title}!</b>

<b>ᴡᴇ ᴀʀᴇ ɢʟᴀᴅ ᴛᴏ ʜᴀᴠᴇ ʏᴏᴜ ʜᴇʀᴇ. ꜰᴇᴇʟ ꜰʀᴇᴇ ᴛᴏ ᴀꜱᴋ ǫᴜᴇꜱᴛɪᴏɴꜱ ᴀɴᴅ ᴇɴᴊᴏʏ ʏᴏᴜʀ ꜱᴛᴀʏ!</b>

<b>💡 ᴛɪᴘ:</b> ᴜꜱᴇ /help ᴛᴏ ꜱᴇᴇ ᴀʟʟ ᴀᴠᴀɪʟᴀʙʟᴇ ᴄᴏᴍᴍᴀɴᴅꜱ.
"""
            
            try:
                # Try to send photo first
                await update.message.reply_photo(
                    photo=welcome_photo,
                    caption=welcome_text,
                    parse_mode=ParseMode.HTML
                )
            except:
                try:
                    # If photo fails, try video
                    await update.message.reply_video(
                        video=welcome_video,
                        caption=welcome_text,
                        parse_mode=ParseMode.HTML
                    )
                except:
                    # If both fail, send text only
                    await update.message.reply_text(
                        text=welcome_text,
                        parse_mode=ParseMode.HTML
                    )

# Callback query handler
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
                # 2x2 grid layout
                keyboard = []
                for i in range(0, len(not_joined), 2):
                    row = []
                    for j in range(2):
                        if i + j < len(not_joined):
                            channel = not_joined[i + j]
                            button_text = f"➕ {channel['title']}"
                            row.append(InlineKeyboardButton(button_text, url=channel['invite_link']))
                    if row:
                        keyboard.append(row)
                
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
    
    elif query.data.startswith("welcome_toggle_"):
        parts = query.data.split("_")
        if len(parts) >= 4:
            group_id = int(parts[2])
            action = parts[3]
            
            # Check if user is group admin or bot admin
            is_group_admin = False
            try:
                chat_member = await context.bot.get_chat_member(group_id, user.id)
                is_group_admin = chat_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
            except:
                pass
            
            if not (is_group_admin or is_admin(user.id)):
                await query.answer("❌ ʏᴏᴜ ᴍᴜꜱᴛ ʙᴇ ᴀɴ ᴀᴅᴍɪɴ ᴛᴏ ᴜꜱᴇ ᴛʜɪꜱ.", show_alert=True)
                return
            
            if action == "on":
                new_status = True
                status_text = "ᴇɴᴀʙʟᴇᴅ ✅"
                action_text = "ᴇɴᴀʙʟᴇᴅ"
            else:
                new_status = False
                status_text = "ᴅɪꜱᴀʙʟᴇᴅ ❌"
                action_text = "ᴅɪꜱᴀʙʟᴇᴅ"
            
            set_group_welcome_status(group_id, new_status)
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ ᴇɴᴀʙʟᴇ", callback_data=f"welcome_toggle_{group_id}_on"),
                    InlineKeyboardButton("❌ ᴅɪꜱᴀʙʟᴇ", callback_data=f"welcome_toggle_{group_id}_off")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=f"✅ <b>ɢʀᴏᴜᴘ ᴡᴇʟᴄᴏᴍᴇ ᴍᴇꜱꜱᴀɢᴇꜱ {action_text}.</b>\n\n"
                     f"<b>👤 ᴄʜᴀɴɢᴇᴅ ʙʏ:</b> {user.mention_html()}\n"
                     f"<b>📊 ꜱᴛᴀᴛᴜꜱ:</b> {status_text}\n\n"
                     f"<b>ᴜꜱᴇ ᴛʜᴇ ʙᴜᴛᴛᴏɴꜱ ʙᴇʟᴏᴡ ᴛᴏ ᴄʜᴀɴɢᴇ ᴀɢᴀɪɴ:</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
    
    elif query.data == "search_services":
        if chat.type == "private":
            # Private chat - show inline buttons for all services
            keyboard = [
                [
                    InlineKeyboardButton("📱 ᴍᴏʙɪʟᴇ", callback_data="service_num"),
                    InlineKeyboardButton("🆔 ᴀᴀᴅʜᴀʀ", callback_data="service_aadhar")
                ],
                [
                    InlineKeyboardButton("🌐 ɪᴘ", callback_data="service_ip"),
                    InlineKeyboardButton("🚗 ᴠᴇʜɪᴄʟᴇ", callback_data="service_vehicle")
                ],
                [
                    InlineKeyboardButton("📱 ᴛɢ", callback_data="service_tg"),
                    InlineKeyboardButton("📸 ɪɴꜱᴛᴀ", callback_data="service_insta")
                ],
                [
                    InlineKeyboardButton("🏢 ɢꜱᴛ", callback_data="service_gst"),
                    InlineKeyboardButton("🏦 ɪꜰꜱᴄ", callback_data="service_ifsc")
                ],
                [
                    InlineKeyboardButton("🇵🇰 ᴘᴀᴋ", callback_data="service_pak"),
                    InlineKeyboardButton("🎮 ꜰꜰɪɴꜰᴏ", callback_data="service_ffinfo")
                ],
                [
                    InlineKeyboardButton("🚗 ᴠɴᴜᴍ", callback_data="service_vnum"),
                    InlineKeyboardButton("🏢 ʀᴛᴏ", callback_data="service_rto")
                ],
                [
                    InlineKeyboardButton("🔓 ʟᴇᴀᴋ", callback_data="service_leak"),
                    InlineKeyboardButton("📱 ɪᴍᴇɪ", callback_data="service_imei")
                ],
                [
                    InlineKeyboardButton("📧 ᴍᴀɪʟ", callback_data="service_mail"),
                    InlineKeyboardButton("🎮 ꜰꜰᴜɪᴅ", callback_data="service_ffuid")
                ],
                [
                    InlineKeyboardButton("💰 ᴄʀᴇᴅɪᴛꜱ", callback_data="check_credits"),
                    InlineKeyboardButton("📊 ꜱᴛᴀᴛꜱ", callback_data="check_stats")
                ],
                [
                    InlineKeyboardButton("🤖 ᴜꜱᴇ ᴍᴇ ʜᴇʀᴇ", url="https://t.me/zionix_chats"),
                    InlineKeyboardButton("📨 ᴜꜱᴇ ɪɴ ᴘᴍ", url=f"https://t.me/{context.bot.username}?start")
                ],
                [
                    InlineKeyboardButton("➕ ᴀᴅᴅ ᴛᴏ ɢʀᴏᴜᴘ", url=f"https://t.me/{context.bot.username}?startgroup=true"),
                    InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="back_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.edit_message_caption(
                    caption="<b>🔍 ꜱᴇʟᴇᴄᴛ ᴀ ꜱᴇᴀʀᴄʜ ꜱᴇʀᴠɪᴄᴇ</b>",
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
            except:
                await query.edit_message_text(
                    text="<b>🔍 ꜱᴇʟᴇᴄᴛ ᴀ ꜱᴇᴀʀᴄʜ ꜱᴇʀᴠɪᴄᴇ</b>",
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
        else:
            # Group chat - show command list
            commands_text = """
<b>🔍 ᴀᴠᴀɪʟᴀʙʟᴇ ᴄᴏᴍᴍᴀɴᴅꜱ:</b>

<code>/num [ᴘʜᴏɴᴇ]</code> - ᴍᴏʙɪʟᴇ ɴᴜᴍʙᴇʀ ʟᴏᴏᴋᴜᴘ
<code>/aadhar [ɪᴅ]</code> - ᴀᴀᴅʜᴀʀ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ
<code>/ip [ᴀᴅᴅʀᴇꜱꜱ]</code> - ɪᴘ ɪɴꜰᴏʀᴍᴀᴛɪᴏɴ
<code>/vehicle [ʀᴇɢ]</code> - ᴠᴇʜɪᴄʟᴇ ᴅᴇᴛᴀɪʟꜱ
<code>/tg [ᴜꜱᴇʀ]</code> - ᴛᴇʟᴇɢʀᴀᴍ ᴜꜱᴇʀ ɪɴꜰᴏ
<code>/insta [ᴜꜱᴇʀ]</code> - ɪɴꜱᴛᴀɢʀᴀᴍ ᴘʀᴏꜰɪʟᴇ
<code>/gst [ɴᴜᴍʙᴇʀ]</code> - ɢꜱᴛ ᴅᴇᴛᴀɪʟꜱ
<code>/ifsc [ᴄᴏᴅᴇ]</code> - ɪꜰꜱᴄ ʟᴏᴏᴋᴜᴘ
<code>/mail [ᴇᴍᴀɪʟ]</code> - ᴇᴍᴀɪʟ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ
<code>/ffuid [ᴜɪᴅ]</code> - ꜰʀᴇᴇ ꜰɪʀᴇ ᴜꜱᴇʀ ɪᴅ
<code>/pak [ɴᴜᴍʙᴇʀ]</code> - ᴘᴀᴋɪꜱᴛᴀɴ ɴᴜᴍʙᴇʀ ʟᴏᴏᴋᴜᴘ
<code>/ffinfo [ᴜɪᴅ]</code> - ꜰʀᴇᴇ ꜰɪʀᴇ ɪɴꜰᴏ
<code>/vnum [ᴠᴇʜɪᴄʟᴇ]</code> - ᴠᴇʜɪᴄʟᴇ ᴏᴡɴᴇʀ
<code>/rto [ᴠᴇʜɪᴄʟᴇ]</code> - ʀᴛᴏ ᴠᴇʜɪᴄʟᴇ ɪɴꜰᴏ
<code>/leak [ɪᴅ]</code> - ʟᴇᴀᴋᴇᴅ ᴅᴀᴛᴀ ꜱᴇᴀʀᴄʜ
<code>/imei [ɴᴜᴍʙᴇʀ]</code> - ɪᴍᴇɪ ɴᴜᴍʙᴇʀ ʟᴏᴏᴋᴜᴘ
<code>/stats</code> - ꜱʜᴏᴡ ʏᴏᴜʀ ꜱᴛᴀᴛꜱ
<code>/credits</code> - ᴄʜᴇᴄᴋ ʏᴏᴜʀ ᴄʀᴇᴅɪᴛꜱ
<code>/welcome</code> - ᴛᴏɢɢʟᴇ ᴡᴇʟᴄᴏᴍᴇ ᴍᴇꜱꜱᴀɢᴇꜱ (ɢʀᴏᴜᴘ ᴀᴅᴍɪɴꜱ ᴏɴʟʏ)
"""
            
            keyboard = [
                [
                    InlineKeyboardButton("🤖 ᴜꜱᴇ ᴍᴇ ʜᴇʀᴇ", url="https://t.me/zionix_chats"),
                    InlineKeyboardButton("📨 ᴜꜱᴇ ɪɴ ᴘᴍ", url=f"https://t.me/{context.bot.username}?start")
                ],
                [
                    InlineKeyboardButton("➕ ᴀᴅᴅ ᴛᴏ ɢʀᴏᴜᴘ", url=f"https://t.me/{context.bot.username}?startgroup=true"),
                    InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="back_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=commands_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
    
    elif query.data == "check_credits":
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
                InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="back_main")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_caption(
                caption=credits_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
        except:
            await query.edit_message_text(
                text=credits_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
    
    elif query.data == "check_stats":
        user_stats = get_user_stats(user.id)
        
        if user_stats:
            total_searches = user_stats['total_searches'] or 0
            join_date = user_stats['join_date']
            credits = user_stats['credits'] or 0
            referrals = user_stats['referrals'] or 0
            
            try:
                join_dt = datetime.strptime(join_date, '%Y-%m-%d %H:%M:%S')
                days_active = (datetime.now() - join_dt).days
            except:
                days_active = 0
            
            stats_text = f"""
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>📊 ʏᴏᴜʀ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>

👤 <b>ᴜꜱᴇʀ:</b> {user.first_name}
🆔 <b>ɪᴅ:</b> <code>{user.id}</code>
📅 <b>ᴊᴏɪɴᴇᴅ:</b> <code>{join_date}</code>
📆 <b>ᴅᴀʏꜱ ᴀᴄᴛɪᴠᴇ:</b> <code>{days_active}</code>
🔍 <b>ᴛᴏᴛᴀʟ ꜱᴇᴀʀᴄʜᴇꜱ:</b> <code>{total_searches}</code>
💰 <b>ᴄʀᴇᴅɪᴛꜱ:</b> <code>{credits}</code>
👥 <b>ʀᴇꜰᴇʀʀᴀʟꜱ:</b> <code>{referrals}</code>
🔗 <b>ʀᴇꜰᴇʀʀᴀʟ ʟɪɴᴋ:</b>
<code>https://t.me/{context.bot.username}?start={user.id}</code>
"""
        else:
            stats_text = "❌ <b>ɴᴏ ꜱᴛᴀᴛꜱ ꜰᴏᴜɴᴅ. ᴘʟᴇᴀꜱᴇ ᴜꜱᴇ /ꜱᴛᴀʀᴛ ꜰɪʀꜱᴛ.</b>"
        
        keyboard = [
            [
                InlineKeyboardButton("🤖 ᴜꜱᴇ ᴍᴇ ʜᴇʀᴇ", url="https://t.me/zionix_chats"),
                InlineKeyboardButton("📨 ᴜꜱᴇ ɪɴ ᴘᴍ", url=f"https://t.me/{context.bot.username}?start")
            ],
            [
                InlineKeyboardButton("➕ ᴀᴅᴅ ᴛᴏ ɢʀᴏᴜᴘ", url=f"https://t.me/{context.bot.username}?startgroup=true"),
                InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="back_main")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_caption(
                caption=stats_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
        except:
            await query.edit_message_text(
                text=stats_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
    
    elif query.data == "help":
        await help_command(update, context)
    
    elif query.data == "donate":
        await donate_command(update, context)
    
    elif query.data.startswith("service_"):
        service = query.data.replace("service_", "")
        services = {
            "num": "📱 ᴍᴏʙɪʟᴇ ɴᴜᴍʙᴇʀ ʟᴏᴏᴋᴜᴘ\n\nᴘʟᴇᴀꜱᴇ ʀᴇᴘʟʏ ᴡɪᴛʜ ᴛʜᴇ ᴘʜᴏɴᴇ ɴᴜᴍʙᴇʀ:",
            "aadhar": "🆔 ᴀᴀᴅʜᴀʀ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ\n\nᴘʟᴇᴀꜱᴇ ʀᴇᴘʟʏ ᴡɪᴛʜ ᴀᴀᴅʜᴀʀ ɴᴜᴍʙᴇʀ:",
            "ip": "🌐 ɪᴘ ᴀᴅᴅʀᴇꜱꜱ ʟᴏᴏᴋᴜᴘ\n\nᴘʟᴇᴀꜱᴇ ʀᴇᴘʟʏ ᴡɪᴛʜ ɪᴘ ᴀᴅᴅʀᴇꜱꜱ:",
            "vehicle": "🚗 ᴠᴇʜɪᴄʟᴇ ᴅᴇᴛᴀɪʟꜱ\n\nᴘʟᴇᴀꜱᴇ ʀᴇᴘʟʏ ᴡɪᴛʜ ᴠᴇʜɪᴄʟᴇ ɴᴜᴍʙᴇʀ:",
            "tg": "📱 ᴛᴇʟᴇɢʀᴀᴍ ᴜꜱᴇʀ ɪɴꜰᴏ\n\nᴘʟᴇᴀꜱᴇ ʀᴇᴘʟʏ ᴡɪᴛʜ ᴛᴇʟᴇɢʀᴀᴍ ᴜꜱᴇʀɴᴀᴍᴇ/ɪᴅ:",
            "insta": "📸 ɪɴꜱᴛᴀɢʀᴀᴍ ᴘʀᴏꜰɪʟᴇ\n\nᴘʟᴇᴀꜱᴇ ʀᴇᴘʟʏ ᴡɪᴛʜ ɪɴꜱᴛᴀɢʀᴀᴍ ᴜꜱᴇʀɴᴀᴍᴇ:",
            "gst": "🏢 ɢꜱᴛ ᴅᴇᴛᴀɪʟꜱ\n\nᴘʟᴇᴀꜱᴇ ʀᴇᴘʟʏ ᴡɪᴛʜ ɢꜱᴛ ɴᴜᴍʙᴇʀ:",
            "ifsc": "🏦 ɪꜰꜱᴄ ᴄᴏᴅᴇ ʟᴏᴏᴋᴜᴘ\n\nᴘʟᴇᴀꜱᴇ ʀᴇᴘʟʏ ᴡɪᴛʜ ɪꜰꜱᴄ ᴄᴏᴅᴇ:",
            "mail": "📧 ᴇᴍᴀɪʟ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ\n\nᴘʟᴇᴀꜱᴇ ʀᴇᴘʟʏ ᴡɪᴛʜ ᴇᴍᴀɪʟ ᴀᴅᴅʀᴇꜱꜱ:",
            "ffuid": "🎮 ꜰʀᴇᴇ ꜰɪʀᴇ ᴜꜱᴇʀ ɪᴅ\n\nᴘʟᴇᴀꜱᴇ ʀᴇᴘʟʏ ᴡɪᴛʜ ꜰꜰ ᴜɪᴅ:",
            "pak": "🇵🇰 ᴘᴀᴋɪꜱᴛᴀɴ ɴᴜᴍʙᴇʀ ʟᴏᴏᴋᴜᴘ\n\nᴘʟᴇᴀꜱᴇ ʀᴇᴘʟʏ ᴡɪᴛʜ ᴘᴀᴋɪꜱᴛᴀɴ ᴘʜᴏɴᴇ ɴᴜᴍʙᴇʀ:",
            "ffinfo": "🎮 ꜰʀᴇᴇ ꜰɪʀᴇ ɪɴꜰᴏ\n\nᴘʟᴇᴀꜱᴇ ʀᴇᴘʟʏ ᴡɪᴛʜ ꜰʀᴇᴇ ꜰɪʀᴇ ᴜɪᴅ:",
            "vnum": "🚗 ᴠᴇʜɪᴄʟᴇ ɴᴜᴍʙᴇʀ ᴏᴡɴᴇʀ\n\nᴘʟᴇᴀꜱᴇ ʀᴇᴘʟʏ ᴡɪᴛʜ ᴠᴇʜɪᴄʟᴇ ɴᴜᴍʙᴇʀ:",
            "rto": "🏢 ʀᴛᴏ ᴠᴇʜɪᴄʟᴇ ɪɴꜰᴏ\n\nᴘʟᴇᴀꜱᴇ ʀᴇᴘʟʏ ᴡɪᴛʜ ᴠᴇʜɪᴄʟᴇ ɴᴜᴍʙᴇʀ:",
            "leak": "🔓 ʟᴇᴀᴋᴇᴅ ᴅᴀᴛᴀ ꜱᴇᴀʀᴄʜ\n\nᴘʟᴇᴀꜱᴇ ʀᴇᴘʟʏ ᴡɪᴛʜ ꜱᴇᴀʀᴄʜ ɪᴅ (ɴᴜᴍʙᴇʀ, ᴀᴀᴅʜᴀʀ, ɴᴀᴍᴇ):",
            "imei": "📱 ɪᴍᴇɪ ɴᴜᴍʙᴇʀ ʟᴏᴏᴋᴜᴘ\n\nᴘʟᴇᴀꜱᴇ ʀᴇᴘʟʏ ᴡɪᴛʜ ɪᴍᴇɪ ɴᴜᴍʙᴇʀ:"
        }
        
        context.user_data['waiting_for'] = service
        await query.message.reply_text(
            services.get(service, "ꜱᴇʀᴠɪᴄᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ"),
            parse_mode=ParseMode.HTML
        )
    
    elif query.data == "back_main":
        # Return to main menu
        if chat.type == "private":
            try:
                welcome_text = f"""
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>🌟 ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴢɪᴏɴɪx ᴏꜱɪɴᴛ ʙᴏᴛ</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>

<b>ᴜꜱᴇ ᴛʜᴇ ʙᴜᴛᴛᴏɴꜱ ʙᴇʟᴏᴡ ᴛᴏ ɴᴀᴠɪɢᴀᴛᴇ:</b>
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
                    ],
                    [
                        InlineKeyboardButton("💝 ᴅᴏɴᴀᴛᴇ", callback_data="donate"),
                        InlineKeyboardButton("📚 ʜᴇʟᴝ", callback_data="help")
                    ]
                ]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                try:
                    await query.edit_message_media(
                        media=InputMediaPhoto(
                            media="https://t.me/imgsrcvvv/2",
                            caption=welcome_text,
                            parse_mode=ParseMode.HTML
                        ),
                        reply_markup=reply_markup
                    )
                except:
                    await query.edit_message_text(
                        text=welcome_text,
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.HTML
                    )
            except Exception as e:
                logger.error(f"Error in back_main: {e}")

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
        elif service == "mail":
            await mail_command_handler(update, context, query)
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
async def num_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, phone: str):
    """Handle num command from inline"""
    try:
        response = requests.get(f"{APIS['num']}{phone}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            await send_api_result(update, context, "num", phone, data)
        else:
            raise Exception("API Error")
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ <code>ᴇʀʀᴏʀ</code>ᴊᴏɪɴ @zionixportal ꜰᴏʀ ꜰᴜʀᴛʜᴇʀ ᴜᴘᴅᴀᴛᴇꜱ",
            parse_mode=ParseMode.HTML
        )

async def aadhar_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, aadhar_id: str):
    """Handle aadhar command from inline"""
    try:
        response = requests.get(f"{APIS['aadhar']}{aadhar_id}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            await send_api_result(update, context, "aadhar", aadhar_id, data)
        else:
            raise Exception("API Error")
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ <code>ᴇʀʀᴏʀ</code>ᴊᴏɪɴ @zionixportal ꜰᴏʀ ꜰᴜʀᴛʜᴇʀ ᴜᴘᴅᴀᴛᴇꜱ",
            parse_mode=ParseMode.HTML
        )

async def ip_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, ip_address: str):
    """Handle ip command from inline"""
    try:
        response = requests.get(f"{APIS['ip']}{ip_address}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            await send_api_result(update, context, "ip", ip_address, data)
        else:
            raise Exception("API Error")
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ <code>ᴇʀʀᴏʀ</code>ᴊᴏɪɴ @zionixportal ꜰᴏʀ ꜰᴜʀᴛʜᴇʀ ᴜᴘᴅᴀᴛᴇꜱ",
            parse_mode=ParseMode.HTML
        )

async def vehicle_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, vehicle_no: str):
    """Handle vehicle command from inline"""
    try:
        response = requests.get(f"{APIS['vehicle']}{vehicle_no}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            await send_api_result(update, context, "vehicle", vehicle_no, data)
        else:
            raise Exception("API Error")
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ <code>ᴇʀʀᴏʀ</code>ᴊᴏɪɴ @zionixportal ꜰᴏʀ ꜰᴜʀᴛʜᴇʀ ᴜᴘᴅᴀᴛᴇꜱ",
            parse_mode=ParseMode.HTML
        )

async def tg_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, username: str):
    """Handle tg command from inline"""
    try:
        response = requests.get(f"{APIS['tg']}{username}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            await send_api_result(update, context, "tg", username, data)
        else:
            raise Exception("API Error")
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ <code>ᴇʀʀᴏʀ</code>ᴊᴏɪɴ @zionixportal ꜰᴏʀ ꜰᴜʀᴛʜᴇʀ ᴜᴘᴅᴀᴛᴇꜱ",
            parse_mode=ParseMode.HTML
        )

async def insta_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, username: str):
    """Handle insta command from inline"""
    try:
        response = requests.get(f"{APIS['insta']}{username}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            await send_api_result(update, context, "insta", username, data)
        else:
            raise Exception("API Error")
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ <code>ᴇʀʀᴏʀ</code>ᴊᴏɪɴ @zionixportal ꜰᴏʀ ꜰᴜʀᴛʜᴇʀ ᴜᴘᴅᴀᴛᴇꜱ",
            parse_mode=ParseMode.HTML
        )

async def gst_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, gst_no: str):
    """Handle gst command from inline"""
    try:
        response = requests.get(f"{APIS['gst']}{gst_no}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            await send_api_result(update, context, "gst", gst_no, data)
        else:
            raise Exception("API Error")
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ <code>ᴇʀʀᴏʀ</code>ᴊᴏɪɴ @zionixportal ꜰᴏʀ ꜰᴜʀᴛʜᴇʀ ᴜᴘᴅᴀᴛᴇꜱ",
            parse_mode=ParseMode.HTML
        )

async def ifsc_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, ifsc_code: str):
    """Handle ifsc command from inline"""
    try:
        response = requests.get(f"{APIS['ifsc']}{ifsc_code}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            await send_api_result(update, context, "ifsc", ifsc_code, data)
        else:
            raise Exception("API Error")
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ <code>ᴇʀʀᴏʀ</code>ᴊᴏɪɴ @zionixportal ꜰᴏʀ ꜰᴜʀᴛʜᴇʀ ᴜᴘᴅᴀᴛᴇꜱ",
            parse_mode=ParseMode.HTML
        )

async def mail_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, email: str):
    """Handle mail command from inline"""
    try:
        response = requests.get(f"{APIS['mail']}{email}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            await send_api_result(update, context, "mail", email, data)
        else:
            raise Exception("API Error")
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ <code>ᴇʀʀᴏʀ</code>ᴊᴏɪɴ @zionixportal ꜰᴏʀ ꜰᴜʀᴛʜᴇʀ ᴜᴘᴅᴀᴛᴇꜱ",
            parse_mode=ParseMode.HTML
        )

async def ffuid_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, ffuid: str):
    """Handle ffuid command from inline"""
    try:
        response = requests.get(f"{APIS['ffuid']}{ffuid}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            await send_api_result(update, context, "ffuid", ffuid, data)
        else:
            raise Exception("API Error")
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ <code>ᴇʀʀᴏʀ</code>\nᴊᴏɪɴ @zionixportal ꜰᴏʀ ꜰᴜʀᴛʜᴇʀ ᴜᴘᴅᴀᴛᴇꜱ",
            parse_mode=ParseMode.HTML
        )

# Command handlers (main commands)
async def num_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /num command"""
    if not await force_join_check(update, context):
        return
    
    if not context.args:
        await update.message.reply_text("ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴘʜᴏɴᴇ ɴᴜᴍʙᴇʀ.\nᴜꜱᴀɢᴇ: <code>/num 9112345678</code>", 
                                      parse_mode=ParseMode.HTML)
        return
    
    phone = context.args[0]
    await num_command_handler(update, context, phone)

async def aadhar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /aadhar command"""
    if not await force_join_check(update, context):
        return
    
    if not context.args:
        await update.message.reply_text("ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ᴀᴀᴅʜᴀʀ ɴᴜᴍʙᴇʀ.\nᴜꜱᴀɢᴇ: <code>/aadhar 123412341234</code>", 
                                      parse_mode=ParseMode.HTML)
        return
    
    aadhar_id = context.args[0]
    await aadhar_command_handler(update, context, aadhar_id)

async def ip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ip command"""
    if not await force_join_check(update, context):
        return
    
    if not context.args:
        await update.message.reply_text("ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ɪᴘ ᴀᴅᴅʀᴇꜱꜱ.\nᴜꜱᴀɢᴇ: <code>/ip 8.8.8.8</code>", 
                                      parse_mode=ParseMode.HTML)
        return
    
    ip_address = context.args[0]
    await ip_command_handler(update, context, ip_address)

async def vehicle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /vehicle command"""
    if not await force_join_check(update, context):
        return
    
    if not context.args:
        await update.message.reply_text("ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ᴠᴇʜɪᴄʟᴇ ɴᴜᴍʙᴇʀ.\nᴜꜱᴀɢᴇ: <code>/vehicle GJ01KV0002</code>", 
                                      parse_mode=ParseMode.HTML)
        return
    
    vehicle_no = context.args[0]
    await vehicle_command_handler(update, context, vehicle_no)

async def tg_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /tg command"""
    if not await force_join_check(update, context):
        return
    
    if not context.args:
        await update.message.reply_text("ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ᴛᴇʟᴇɢʀᴀᴍ ᴜꜱᴇʀɴᴀᴍᴇ/ɪᴅ.\nᴜꜱᴀɢᴇ: <code>/tg username</code>", 
                                      parse_mode=ParseMode.HTML)
        return
    
    username = context.args[0]
    await tg_command_handler(update, context, username)

async def insta_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /insta command"""
    if not await force_join_check(update, context):
        return
    
    if not context.args:
        await update.message.reply_text("ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ɪɴꜱᴛᴀɢʀᴀᴍ ᴜꜱᴇʀɴᴀᴍᴇ.\nᴜꜱᴀɢᴇ: <code>/insta username</code>", 
                                      parse_mode=ParseMode.HTML)
        return
    
    username = context.args[0]
    await insta_command_handler(update, context, username)

async def gst_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /gst command"""
    if not await force_join_check(update, context):
        return
    
    if not context.args:
        await update.message.reply_text("ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴟᴏᴠɪᴅᴇ ɢꜱᴛ ɴᴜᴍʙᴇʀ.\nᴜꜱᴀɢᴇ: <code>/gst 07AAGFF2194N1Z1</code>", 
                                      parse_mode=ParseMode.HTML)
        return
    
    gst_no = context.args[0]
    await gst_command_handler(update, context, gst_no)

async def ifsc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ifsc command"""
    if not await force_join_check(update, context):
        return
    
    if not context.args:
        await update.message.reply_text("ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ɪꜰꜱᴄ ᴄᴏᴅᴇ.\nᴜꜱᴀɢᴇ: <code>/ifsc SBIN0005943</code>", 
                                      parse_mode=ParseMode.HTML)
        return
    
    ifsc_code = context.args[0]
    await ifsc_command_handler(update, context, ifsc_code)

async def mail_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mail command"""
    if not await force_join_check(update, context):
        return
    
    if not context.args:
        await update.message.reply_text("ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ᴇᴍᴀɪʟ ᴀᴅᴅʀᴇꜱꜱ.\nᴜꜱᴀɢᴇ: <code>/mail example@email.com</code>", 
                                      parse_mode=ParseMode.HTML)
        return
    
    email = context.args[0]
    await mail_command_handler(update, context, email)

async def ffuid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ffuid command"""
    if not await force_join_check(update, context):
        return
    
    if not context.args:
        await update.message.reply_text("ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ꜰꜰ ᴜɪᴅ.\nᴜꜱᴀɢᴇ: <code>/ffuid ᴜɪᴅ</code>", 
                                      parse_mode=ParseMode.HTML)
        return
    
    ffuid = context.args[0]
    await ffuid_command_handler(update, context, ffuid)

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

# Donate command
async def donate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send donation information"""
    user = update.effective_user
    chat = update.effective_chat
    
    # Check force join first
    if not await force_join_check(update, context):
        return
    
    try:
        qr_image = "https://i.ibb.co/JwYw1JkD/your-image.jpg"  # Replace with your QR image
        
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
        
        caption = f"""
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>💖 ꜱᴜᴘᴘᴏʀᴛ ᴜꜱ ʙʏ ᴅᴏɴᴀᴛɪɴɢ!</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>

{('👤 <b>ᴜꜱᴇʀ:</b> ' + user.mention_html() + '\n\n') if chat.type != "private" else ''}
<b>📌 ᴜᴘɪ ɪᴅ:</b> <code>6396007@axl</code>

<b>📲 ꜱᴄᴀɴ ᴛʜᴇ ǫʀ ᴄᴏᴅᴇ ʙᴇʟᴏᴡ ᴜꜱɪɴɢ ᴀɴʏ ᴜᴘɪ ᴀᴘᴘ ᴛᴏ ᴅᴏɴᴀᴛᴇ.</b>

<b>🙏 ᴛʜᴀɴᴋ ʏᴏᴜ ꜰᴏʀ ʏᴏᴜʀ ꜱᴜᴘᴘᴏʀᴛ!</b>

<b>⚙️ ᴏʀ ᴛʀʏ ᴏᴜʀ ʙᴏᴛ ᴜꜱɪɴɢ ᴛʜᴇ ᴏᴘᴛɪᴏɴꜱ ʙᴇʟᴏᴡ 👇</b>
"""
        
        if update.callback_query:
            await update.callback_query.message.reply_photo(
                photo=qr_image,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        elif update.message:
            await update.message.reply_photo(
                photo=qr_image,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Error in donate command: {e}")
        donate_text = f"""
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>💖 ꜱᴜᴘᴘᴏʀᴛ ᴜꜱ ʙʏ ᴅᴏɴᴀᴛɪɴɢ!</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━</code>

{('👤 <b>ᴜꜱᴇʀ:</b> ' + user.mention_html() + '\n\n') if chat.type != "private" else ''}
<b>📌 ᴜᴘɪ ɪᴅ:</b> <code>6396007@axl</code>

<b>🙏 ᴛʜᴀɴᴋ ʏᴏᴜ ꜰᴏʀ ʏᴏᴜʀ ꜱᴜᴘᴘᴏʀᴛ!</b>
"""
        
        keyboard = [
            [
                InlineKeyboardButton("🤖 ᴜꜱᴇ ᴍᴇ ʜᴇʀᴇ", url="https://t.me/zionix_chats"),
                InlineKeyboardButton("📨 ᴜꜱᴇ ɪɴ ᴘᴍ", url=f"https://t.me/{context.bot.username}?start")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.message.reply_text(
                text=donate_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        elif update.message:
            await update.message.reply_text(
                text=donate_text,
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
• /mail [ᴇᴍᴀɪʟ] - ᴇᴍᴀɪʟ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ
• /ffuid [ᴜɪᴅ] - ꜰʀᴇᴇ ꜰɪʀᴇ ᴜꜱᴇʀ ɪᴅ
• /pak [ɴᴜᴍʙᴇʀ] - ᴘᴀᴋɪꜱᴛᴀɴ ɴᴜᴍʙᴇʀ ʟᴏᴏᴋᴜᴘ
• /ffinfo [ᴜɪᴅ] - ꜰʀᴇᴇ ꜰɪʀᴇ ɪɴꜰᴏ
• /vnum [ᴠᴇʜɪᴄʟᴇ] - ᴠᴇʜɪᴄʟᴇ ᴏᴡɴᴇʀ
• /rto [ᴠᴇʜɪᴄʟᴇ] - ʀᴛᴏ ᴠᴇʜɪᴄʟᴇ ɪɴꜰᴏ
• /leak [ɪᴅ] - ʟᴇᴀᴋᴇᴅ ᴅᴀᴛᴀ ꜱᴇᴀʀᴄʜ
• /imei [ɴᴜᴍʙᴇʀ] - ɪᴍᴇɪ ɴᴜᴍʙᴇʀ ʟᴏᴏᴋᴜᴘ

<b>👥 ɢʀᴏᴜᴘ ᴄᴏᴍᴍᴀɴᴅꜱ:</b>
• /welcome [ᴏɴ/ᴏꜰꜰ] - ᴛᴏɢɢʟᴇ ᴡᴇʟᴄᴏᴍᴇ ᴍᴇꜱꜱᴀɢᴇꜱ (ᴀᴅᴍɪɴꜱ ᴏɴʟʏ)

<b>👑 ᴀᴅᴍɪɴ ᴄᴏᴍᴍᴀɴᴅꜱ:</b>
• /broadcast [ᴍꜱɢ] - ʙʀᴏᴀᴅᴄᴀꜱᴛ ᴍᴇꜱꜱᴀɢᴇ
• /ban [ᴜꜱᴇʀ_ɪᴅ] - ʙᴀɴ ᴜꜱᴇʀ
• /unban [ᴜꜱᴇʀ_ɪᴅ] - ᴜɴʙᴀɴ ᴜꜱᴇʀ
• /getdb - ɢᴇᴛ ᴅᴀᴛᴀʙᴀꜱᴇ ꜰɪʟᴇ

<b>💰 ᴄʀᴇᴅɪᴛ ꜱʏꜱᴛᴇᴍ:</b>
• 🎁 5 ᴅᴀɪʟʏ ᴄʀᴇᴅɪᴛꜱ ꜰᴏʀ ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀᴛ
• 🤝 10 ᴄʀᴇᴅɪᴛꜱ ᴘᴇʀ ʀᴇꜰᴇʀʀᴀʟ
• 👥 ᴜɴʟɪᴍɪᴛᴇᴅ ᴄʀᴇᴅɪᴛꜱ ɪɴ ɢʀᴏᴜᴘꜱ
• 🔗 ʀᴇꜰᴇʀʀᴀʟ ʟɪɴᴋ: https://t.me/{context.bot.username}?start={user.id}

<b>⚠️ ɴᴏᴛᴇ:</b> ꜱᴏᴍᴇ ꜱᴇʀᴠɪᴄᴇꜱ ᴍᴀʏ ʜᴀᴠᴇ ᴀᴘɪ ʟɪᴍɪᴛꜱ.
<b>👥 ᴍɪɴɪᴍᴜᴍ ɢʀᴏᴜᴘ ꜱɪᴢᴇ:</b> {MIN_GROUP_MEMBERS} ᴍᴇᴍʙᴇʀꜱ ʀᴇǫᴜɪʀᴇᴅ
<b>📢 ꜰᴏʀᴄᴇ ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟꜱ:</b> @zionixportal, @zionix_portal, @encorexosint, @zionixpy
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

# Admin commands (REMOVED addadmin and addchannel)
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
        BotCommand("mail", "ᴇᴍᴀɪʟ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ"),
        BotCommand("ffuid", "ꜰʀᴇᴇ ꜰɪʀᴇ ᴜꜱᴇʀ ɪᴅ"),
        BotCommand("pak", "ᴘᴀᴋɪꜱᴛᴀɴ ɴᴜᴍʙᴇʀ ʟᴏᴏᴋᴜᴘ"),
        BotCommand("ffinfo", "ꜰʀᴇᴇ ꜰɪʀᴇ ɪɴꜰᴏ"),
        BotCommand("vnum", "ᴠᴇʜɪᴄʟᴇ ɴᴜᴍʙᴇʀ ᴏᴡɴᴇʀ"),
        BotCommand("rto", "ʀᴛᴏ ᴠᴇʜɪᴄʟᴇ ɪɴꜰᴏ"),
        BotCommand("leak", "ʟᴇᴀᴋᴇᴅ ᴅᴀᴛᴀ ꜱᴇᴀʀᴄʜ"),
        BotCommand("imei", "ɪᴍᴇɪ ɴᴜᴍʙᴇʀ ʟᴏᴏᴋᴜᴘ"),
        BotCommand("stats", "ᴠɪᴇᴡ ʏᴏᴜʀ ꜱᴛᴀᴛꜱ"),
        BotCommand("credits", "ᴄʜᴇᴄᴋ ʏᴏᴜʀ ᴄʀᴇᴅɪᴛꜱ"),
        BotCommand("donate", "ꜱᴜᴘᴘᴏʀᴛ ᴛʜᴇ ʙᴏᴛ"),
        BotCommand("welcome", "ᴛᴏɢɢʟᴇ ᴡᴇʟᴄᴏᴍᴇ ᴍᴇꜱꜱᴀɢᴇꜱ")
    ]
    
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
        application.add_handler(CommandHandler("welcome", welcome_command))
        
        # OSINT commands
        application.add_handler(CommandHandler("num", num_command))
        application.add_handler(CommandHandler("aadhar", aadhar_command))
        application.add_handler(CommandHandler("ip", ip_command))
        application.add_handler(CommandHandler("vehicle", vehicle_command))
        application.add_handler(CommandHandler("tg", tg_command))
        application.add_handler(CommandHandler("insta", insta_command))
        application.add_handler(CommandHandler("gst", gst_command))
        application.add_handler(CommandHandler("ifsc", ifsc_command))
        application.add_handler(CommandHandler("mail", mail_command))
        application.add_handler(CommandHandler("ffuid", ffuid_command))
        
        # NEW API commands
        application.add_handler(CommandHandler("pak", pak_command))
        application.add_handler(CommandHandler("ffinfo", ffinfo_command))
        application.add_handler(CommandHandler("vnum", vnum_command))
        application.add_handler(CommandHandler("rto", rto_command))
        application.add_handler(CommandHandler("leak", leak_command))
        application.add_handler(CommandHandler("imei", imei_command))
        
        # Admin commands (REMOVED addadmin and addchannel)
        application.add_handler(CommandHandler("broadcast", broadcast_command))
        application.add_handler(CommandHandler("getdb", getdb_command))
        
        # Callback and message handlers
        application.add_handler(CallbackQueryHandler(button_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_service_response))
        
        # New member handler for welcome messages
        application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_member))
        
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
        print(f"📢 Force Join Channels: {', '.join([ch['username'] for ch in FORCE_CHANNELS])}")
        print("=" * 50)
        print("🚀 Starting bot...")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()