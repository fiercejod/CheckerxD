import os
import json
import zipfile
import tempfile
import asyncio
import logging
from io import BytesIO
import aiohttp
import shutil
import time
import re
import threading
import requests
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters


BOT_VERSION = "1.0.0"
BOT_STATUS = "✅ WORKING"
BOT_OWNER = "@S4J4G"
BOT_CHANNEL = "BasicCoders"
BOT_DEVELOPER = "@Kiltes"


ADMIN_ID = 7875025583


total_working = 0
total_fails = 0
total_unsubscribed = 0
total_checked = 0
lock = threading.Lock()
netflix_hits_folder = "netflix_hits"
netflix_failures_folder = "netflix_failures"
netflix_broken_folder = "netflix_broken"
netflix_free_folder = "netflix_free"


HAVE_PY7ZR = False
HAVE_RARFILE = False
try:
    import py7zr
    HAVE_PY7ZR = True
except ImportError:
    pass
try:
    import rarfile
    HAVE_RARFILE = True
except ImportError:
    pass


def setup_database():
    """Set up the SQLite database for the key system"""
    conn = sqlite3.connect('bot_keys.db')
    cursor = conn.cursor()
    
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS keys (
        key TEXT PRIMARY KEY,
        created_date TEXT,
        expiry_date TEXT,
        max_uses INTEGER,
        uses INTEGER DEFAULT 0,
        created_by TEXT
    )
    ''')
    
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS activated_users (
        user_id INTEGER PRIMARY KEY,
        key TEXT,
        activated_date TEXT,
        expiry_date TEXT,
        FOREIGN KEY (key) REFERENCES keys (key)
    )
    ''')
    
    conn.commit()
    conn.close()

def add_key(key, max_uses=1, expiry_days=30, created_by="admin"):
    """Add a new key to the database"""
    conn = sqlite3.connect('bot_keys.db')
    cursor = conn.cursor()
    
    created_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    expiry_date = (datetime.now() + timedelta(days=expiry_days)).strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        cursor.execute(
            "INSERT INTO keys (key, created_date, expiry_date, max_uses, uses, created_by) VALUES (?, ?, ?, ?, ?, ?)",
            (key, created_date, expiry_date, max_uses, 0, created_by)
        )
        conn.commit()
        result = True
    except sqlite3.IntegrityError:
        result = False
    
    conn.close()
    return result

def delete_key(key):
    """Delete a key from the database"""
    conn = sqlite3.connect('bot_keys.db')
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM keys WHERE key = ?", (key,))
    if cursor.rowcount > 0:
        result = True
    else:
        result = False
    
    conn.commit()
    conn.close()
    return result

def get_all_keys():
    """Get all keys from the database"""
    conn = sqlite3.connect('bot_keys.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT key, created_date, expiry_date, max_uses, uses, created_by FROM keys")
    keys = cursor.fetchall()
    
    conn.close()
    return keys

def is_key_valid(key):
    """Check if a key is valid"""
    conn = sqlite3.connect('bot_keys.db')
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT expiry_date, max_uses, uses FROM keys WHERE key = ?", 
        (key,)
    )
    key_data = cursor.fetchone()
    conn.close()
    
    if not key_data:
        return False
    
    expiry_date, max_uses, uses = key_data
    
    
    if datetime.now() > datetime.strptime(expiry_date, "%Y-%m-%d %H:%M:%S"):
        return False
    
    
    if uses >= max_uses:
        return False
    
    return True

def activate_user(user_id, key):
    """Activate a user with a key"""
    if not is_key_valid(key):
        return False
    
    conn = sqlite3.connect('bot_keys.db')
    cursor = conn.cursor()
    
    
    cursor.execute("SELECT user_id FROM activated_users WHERE user_id = ?", (user_id,))
    if cursor.fetchone():
        conn.close()
        return "already_activated"
    
    
    cursor.execute("SELECT expiry_date FROM keys WHERE key = ?", (key,))
    key_data = cursor.fetchone()
    
    if not key_data:
        conn.close()
        return False
    
    expiry_date = key_data[0]
    activated_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
   
    cursor.execute(
        "INSERT INTO activated_users (user_id, key, activated_date, expiry_date) VALUES (?, ?, ?, ?)",
        (user_id, key, activated_date, expiry_date)
    )
    
    
    cursor.execute("UPDATE keys SET uses = uses + 1 WHERE key = ?", (key,))
    
    conn.commit()
    conn.close()
    return True

def is_user_activated(user_id):
    """Check if a user is activated"""
    
    if user_id == ADMIN_ID:
        return True
        
    conn = sqlite3.connect('bot_keys.db')
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT expiry_date FROM activated_users WHERE user_id = ?", 
        (user_id,)
    )
    user_data = cursor.fetchone()
    conn.close()
    
    if not user_data:
        return False
    
    expiry_date = user_data[0]
    
    
    if datetime.now() > datetime.strptime(expiry_date, "%Y-%m-%d %H:%M:%S"):
        return False
    
    return True




def plan_name_mapping(plan):
    mapping = {
        "duo_premium": "Duo Premium",
        "family_premium_v2": "Family Premium",
        "premium": "Premium",
        "premium_mini": "Premium Mini",
        "student_premium": "Student Premium",
        "student_premium_hulu": "Student Premium + Hulu",
        "free": "Free"
    }
    return mapping.get(plan, "Unknown")


def format_cookie_file(data, cookie_content):
    plan = plan_name_mapping(data.get("currentPlan", "unknown"))
    country = data.get("country", "unknown")
    auto_pay = "True" if data.get("isRecurring", False) else "False"
    trial = "True" if data.get("isTrialUser", False) else "False"

    header = f"PLAN = {plan}\nCOUNTRY = {country}\nAutoPay = {auto_pay}\nTrial = {trial}\nChecker By: {BOT_OWNER}\nSpotify COOKIE :👇\n\n\n"
    return header + cookie_content


def string_to_bool(s):
    return s.upper() == "TRUE"

def bool_to_string(s):
    return "TRUE" if s else "FALSE"

def convert_to_netscape_format(cookie):
    """Convert the cookie dictionary to the Netscape cookie format string"""
    return "{}\t{}\t{}\t{}\t{}\t{}\t{}".format(
        cookie['domain'],
        'TRUE' if cookie['flag'].upper() == 'TRUE' else 'FALSE',
        cookie['path'],
        'TRUE' if cookie['secure'] else 'FALSE',
        cookie['expiration'],
        cookie['name'],
        cookie['value']
    )

def load_netflix_cookies_from_file(cookie_file):
    """Load cookies from a given file and return a dictionary of cookies."""
    cookies = {}
    try:
        with open(cookie_file, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) >= 7:
                    domain, _, path, secure, expires, name, value = parts[:7]
                    cookies[name] = value
    except Exception as e:
        print(f"Error loading cookies from {cookie_file}: {str(e)}")
    return cookies

def make_request_with_cookies(cookies):
    """Make an HTTP request using provided cookies and return the response text."""
    session = requests.Session()
    session.cookies.update(cookies)
    try:
        return session.get("https://www.netflix.com/YourAccount").text
    except Exception as e:
        print(f"Error making request: {str(e)}")
        return ""

def extract_info(response_text):
    """Extract relevant information from the response text."""
    patterns = {
        'countryOfSignup': r'"countryOfSignup":\s*"([^"]+)"',
        'memberSince': r'"memberSince":\s*"([^"]+)"',
        'userGuid': r'"userGuid":\s*"([^"]+)"',
        'showExtraMemberSection': r'"showExtraMemberSection":\s*\{\s*"fieldType":\s*"Boolean",\s*"value":\s*(true|false)',
        'membershipStatus': r'"membershipStatus":\s*"([^"]+)"',
        'maxStreams': r'maxStreams\":\{\"fieldType\":\"Numeric\",\"value\":([^,]+),',
        'localizedPlanName': r'localizedPlanName\":\{\"fieldType\":\"String\",\"value\":\"([^"]+)\"'
    }

    extracted_info = {key: re.search(pattern, response_text).group(1) if re.search(pattern, response_text) else None for key, pattern in patterns.items()}

    if extracted_info['localizedPlanName']:
        extracted_info['localizedPlanName'] = extracted_info['localizedPlanName'].replace('x28', '').replace('\\', ' ').replace('x20', '').replace('x29', '')

    if extracted_info['memberSince']:
        extracted_info['memberSince'] = extracted_info['memberSince'].replace("\\x20", " ")

    return extracted_info

def format_netflix_cookie(info, cookie_content):
    plan_name = info.get('localizedPlanName', 'Unknown').replace("miembro u00A0extra", "(Extra Member)")
    member_since = info.get('memberSince', 'Unknown').replace("\x20", " ")
    max_streams = info.get('maxStreams', 'Unknown')
    
    if max_streams:
        max_streams = max_streams.rstrip('}')
    
    extra_members = "Unknown"
    if info.get('showExtraMemberSection') == "true":
        extra_members = "Yes✅"
    elif info.get('showExtraMemberSection') == "false":
        extra_members = "No❌"
    
    header = (
        f"Plan: {plan_name}\n"
        f"Country: {info.get('countryOfSignup', 'Unknown')}\n"
        f"Member since: {member_since}\n"
        f"Max Streams: {max_streams}\n"
        f"Extra members: {extra_members}\n"
        f"Checker By: {BOT_OWNER}\n"
        f"Netflix Cookie 👇\n\n\n"
    )
    
    return header + cookie_content


def generate_start_message(user_first_name=None):
    formats = ["TXT", "Netscape/JSON", "ZIP"]
    if HAVE_PY7ZR:
        formats.append("7Z")
    if HAVE_RARFILE:
        formats.append("RAR")
    formats_str = ", ".join(formats)

    greeting = f"Welcome, {user_first_name}! " if user_first_name else "Welcome! "

    start_message = (
        f"🎵 COOKIE CHECKER BOT 🎵\n\n"
        f"{greeting}This bot checks Spotify & Netflix cookies to verify if they're valid "
        f"and identifies their subscription plans.\n\n"
        f"📊 BOT INFORMATION\n"
        f"• Version: {BOT_VERSION}\n"
        f"• Status: {BOT_STATUS}\n"
        f"• Owner: {BOT_OWNER}\n"
        f"• Updates: {BOT_CHANNEL}\n"
        f"• Developer: {BOT_DEVELOPER}\n\n"
        f"📁 SUPPORTED FORMATS\n"
        f"• {formats_str}\n\n"
        f"Send a cookie file or archive to start checking!"
    )

    return start_message

def safe_read_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read(), True
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='latin-1') as f:
                return f.read(), True
        except Exception:
            return None, False

async def extract_archive(file_path, extraction_dir, update, processing_msg):
    file_name = os.path.basename(file_path)

    try:
        if file_name.lower().endswith('.zip'):
            await processing_msg.edit_text("Extracting ZIP archive...")
            with zipfile.ZipFile(file_path) as zip_ref:
                zip_ref.extractall(extraction_dir)
            return True
        elif file_name.lower().endswith('.7z') and HAVE_PY7ZR:
            await processing_msg.edit_text("Extracting 7Z archive...")
            with py7zr.SevenZipFile(file_path, mode='r') as z:
                z.extractall(extraction_dir)
            return True
        elif file_name.lower().endswith('.rar') and HAVE_RARFILE:
            await processing_msg.edit_text("Extracting RAR archive...")
            with rarfile.RarFile(file_path) as rf:
                rf.extractall(extraction_dir)
            return True
        else:
            if file_name.lower().endswith('.7z') and not HAVE_PY7ZR:
                await processing_msg.edit_text("7Z not supported. Install py7zr module.")
            elif file_name.lower().endswith('.rar') and not HAVE_RARFILE:
                await processing_msg.edit_text("RAR not supported. Install rarfile module.")
            else:
                await processing_msg.edit_text(
                    "❌ Your file is not supported. We only accept TXT and ZIP files.\n\n"
                    "If your file is in ZIP and still getting this error, it might contain nested folders "
                    "which need to be organized properly."
                )
            return False

    except Exception as e:
        await processing_msg.edit_text(
            f"❌ Error extracting {file_name}:\n{str(e)}\n\n"
            "Make sure your archive is not corrupted and contains cookie files directly "
            "or in a simple folder structure."
        )
        return False

def get_all_files(directory):
    all_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            all_files.append(os.path.join(root, file))
    return all_files

def generate_spotify_stats(valid_results):
    plans = {}
    countries = {}
    
    for valid in valid_results:
        plan = valid["plan"]
        country = valid["country"]
        
        if plan not in plans:
            plans[plan] = 0
        plans[plan] += 1
        
        if country not in countries:
            countries[country] = 0
        countries[country] += 1
    
    autopay_count = sum(1 for valid in valid_results if valid["auto_pay"])
    trial_count = sum(1 for valid in valid_results if valid["trial"])
    
    plans_str = ", ".join([f"{plan}: {count}" for plan, count in plans.items()])
    top_countries = sorted(countries.items(), key=lambda x: x[1], reverse=True)[:3]
    countries_str = ", ".join([f"{country}: {count}" for country, count in top_countries])
    
    return plans_str, countries_str, autopay_count, trial_count

def generate_netflix_stats(valid_results):
    plans = {}
    countries = {}
    
    for valid in valid_results:
        plan = valid.get("plan", "Unknown")
        country = valid.get("country", "Unknown")
        
        if plan not in plans:
            plans[plan] = 0
        plans[plan] += 1
        
        if country not in countries:
            countries[country] = 0
        countries[country] += 1
    
    extra_members_count = sum(1 for valid in valid_results if valid.get("extra_members") == "true")
    
    plans_str = ", ".join([f"{plan}: {count}" for plan, count in plans.items()])
    top_countries = sorted(countries.items(), key=lambda x: x[1], reverse=True)[:3]
    countries_str = ", ".join([f"{country}: {count}" for country, count in top_countries])
    
    return plans_str, countries_str, extra_members_count

def is_valid_file_type(file_name):
    supported_extensions = ['.txt', '.json', '.cookie', '.cookies', '.netscape']
    _, ext = os.path.splitext(file_name.lower())
    return ext in supported_extensions or ext == ''

def is_archive_file(file_name):
    zip_extension = ['.zip']
    optional_extensions = []
    if HAVE_PY7ZR:
        optional_extensions.append('.7z')
    if HAVE_RARFILE:
        optional_extensions.append('.rar')
    
    supported_archives = zip_extension + optional_extensions
    _, ext = os.path.splitext(file_name.lower())
    return ext in supported_archives



async def check_spotify_cookie_file(file_content, file_name, is_json=False):
    try:
        cookies = {}

        if is_json:
            cookies_json = json.loads(file_content)
            for cookie in cookies_json:
                name = cookie.get('name')
                value = cookie.get('value')
                if name and value:
                    cookies[name] = value
        else:
            for line in file_content.splitlines():
                parts = line.strip().split('\t')
                if len(parts) >= 7:
                    name, value = parts[5], parts[6]
                    cookies[name] = value

        if not cookies:
            return {"status": "error", "message": f"No valid cookies found in {file_name}"}

        async with aiohttp.ClientSession(cookies=cookies) as session:
            headers = {'Accept-Encoding': 'identity'}
            async with session.get("https://www.spotify.com/eg-ar/api/account/v1/datalayer", headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    current_plan = data.get("currentPlan", "unknown")
                    plan_name = plan_name_mapping(current_plan)
                    
                    formatted_cookie = format_cookie_file(data, file_content)
                    
                    return {
                        "status": "valid",
                        "plan": plan_name,
                        "country": data.get("country", "unknown"),
                        "auto_pay": data.get("isRecurring", False),
                        "trial": data.get("isTrialUser", False),
                        "file_name": file_name,
                        "formatted_content": formatted_cookie
                    }
                else:
                    return {"status": "invalid", "message": f"Login failed with {file_name}"}

    except json.JSONDecodeError:
        return {"status": "error", "message": f"Invalid JSON format in {file_name}"}
    except Exception as e:
        return {"status": "error", "message": f"Error processing {file_name}: {str(e)}"}

async def check_netflix_cookie_file(file_content, file_name, is_json=False):
    try:
        cookies = {}

        if is_json:
            cookies_json = json.loads(file_content)
            for cookie in cookies_json:
                name = cookie.get('name')
                value = cookie.get('value')
                if name and value:
                    cookies[name] = value
        else:
            for line in file_content.splitlines():
                parts = line.strip().split('\t')
                if len(parts) >= 7:
                    name, value = parts[5], parts[6]
                    cookies[name] = value

        if not cookies:
            return {"status": "error", "message": f"No valid cookies found in {file_name}"}

        response_text = make_request_with_cookies(cookies)
        if not response_text:
            return {"status": "invalid", "message": f"Login failed with {file_name}"}

        info = extract_info(response_text)
        if info['countryOfSignup'] and info['countryOfSignup'] != "null":
            is_subscribed = info['membershipStatus'] == "CURRENT_MEMBER"
            
            if not is_subscribed:
                return {"status": "unsubscribed", "message": f"Login successful with {file_name} but not subscribed"}
            
            formatted_cookie = format_netflix_cookie(info, file_content)
            
            return {
                "status": "valid",
                "country": info['countryOfSignup'],
                "member_since": info['memberSince'],
                "extra_members": info['showExtraMemberSection'],
                "max_streams": info['maxStreams'],
                "plan": info['localizedPlanName'],
                "file_name": file_name,
                "formatted_content": formatted_cookie
            }
        else:
            return {"status": "invalid", "message": f"Login failed with {file_name}"}

    except json.JSONDecodeError:
        return {"status": "error", "message": f"Invalid JSON format in {file_name}"}
    except Exception as e:
        return {"status": "error", "message": f"Error processing {file_name}: {str(e)}"}




async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_first_name = update.effective_user.first_name if update.effective_user else None
    
    
    activation_status = is_user_activated(user_id)
    
    
    start_message = generate_start_message(user_first_name)
    
    
    if activation_status:
        start_message += "\n\n✅ Your account is activated! You can use all bot features."
    else:
        start_message += "\n\n❌ Your account is not activated. Use /activate YOUR_KEY to gain access."

    keyboard = [
        [
            InlineKeyboardButton("Check Spotify", callback_data="check_spotify"),
            InlineKeyboardButton("Check Netflix", callback_data="check_netflix")
        ],
        [InlineKeyboardButton("Channel", url=f"https://t.me/+NdidYpG9Bh8yZTY1")],
        [InlineKeyboardButton("About", callback_data="about")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(start_message, reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    
    if query.data in ["check_spotify", "check_netflix"]:
        if not is_user_activated(user_id):
            await query.answer("Access restricted! Activate the bot first.")
            await query.edit_message_text(
                "⚠️ Access restricted! You need to activate the bot with a valid key.\n\n"
                "Use /activate YOUR_KEY to activate your access.\n"
                "If you don't have a key, please contact the bot owner."
            )
            return
    
    await query.answer()

    formats_msg = "Supported: TXT, Netscape/JSON cookies, ZIP"
    if HAVE_PY7ZR:
        formats_msg += "/7Z"
    if HAVE_RARFILE:
        formats_msg += "/RAR"

    if query.data == "check_spotify":
        await query.edit_message_text(
            f"Send your Spotify cookie file(s) to check.\n{formats_msg} archives supported.\n\n"
            f"Please make sure you're sending Spotify cookies."
        )
        context.user_data["check_mode"] = "spotify"

    elif query.data == "check_netflix":
        await query.edit_message_text(
            f"Send your Netflix cookie file(s) to check.\n{formats_msg} archives supported.\n\n"
            f"Please make sure you're sending Netflix cookies."
        )
        context.user_data["check_mode"] = "netflix"

    elif query.data == "about":
        about_message = (
            f"🍿 COOKIE CHECKER BOT 🍿\n\n"
            f"This bot helps you verify Spotify and Netflix cookies and identify premium accounts.\n\n"
            f"Version: {BOT_VERSION}\n"
            f"Status: {BOT_STATUS}\n"
            f"Owner: {BOT_OWNER}\n"
            f"Updates: {BOT_CHANNEL}\n"
            f"Developer: {BOT_DEVELOPER}\n\n"
            f"Join our channel for more tools and updates!"
        )

        keyboard = [
            [InlineKeyboardButton("Channel", url=f"https://t.me/{BOT_CHANNEL.replace('@', '')}")],
            [InlineKeyboardButton("Back", callback_data="back_to_start")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(about_message, reply_markup=reply_markup)

    elif query.data == "back_to_start":
        user_first_name = query.from_user.first_name if query.from_user else None
        start_message = generate_start_message(user_first_name)
        
        
        if is_user_activated(user_id):
            start_message += "\n\n✅ Your account is activated! You can use all bot features."
        else:
            start_message += "\n\n❌ Your account is not activated. Use /activate YOUR_KEY to gain access."

        keyboard = [
            [
                InlineKeyboardButton("Check Spotify", callback_data="check_spotify"),
                InlineKeyboardButton("Check Netflix", callback_data="check_netflix")
            ],
            [InlineKeyboardButton("Channel", url=f"https://t.me/{BOT_CHANNEL.replace('@', '')}")],
            [InlineKeyboardButton("About", callback_data="about")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(start_message, reply_markup=reply_markup)

async def process_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    
    if not is_user_activated(user_id):
        await update.message.reply_text(
            "⚠️ Access restricted! You need to activate the bot with a valid key.\n\n"
            "Use /activate YOUR_KEY to activate your access.\n"
            "If you don't have a key, please contact the bot owner."
        )
        return
    
    
    check_mode = context.user_data.get("check_mode", "spotify")
    processing_msg = await update.message.reply_text(f"Processing your {check_mode.capitalize()} cookie file(s)... Please wait.")

    file = await context.bot.get_file(update.message.document.file_id)
    file_name = update.message.document.file_name

    if not (is_valid_file_type(file_name) or is_archive_file(file_name)):
        await processing_msg.edit_text(
            "❌ Your file is not supported. We only accept TXT and ZIP files only.\n\n"
            "Please make sure you're uploading a valid cookie file or archive containing cookie files."
        )
        return

    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, file_name)
    await file.download_to_drive(file_path)

    results = {
        "valid": [],
        "invalid": 0,
        "errors": 0,
        "unsubscribed": 0
    }

    hit_file_path = os.path.join(temp_dir, f"{check_mode.capitalize()}_Hit.txt")
    with open(hit_file_path, "w", encoding="utf-8") as hit_file:
        hit_file.write(f"# {check_mode.upper()} COOKIE CHECKER RESULTS\n")
        hit_file.write(f"# Created by {BOT_OWNER}\n\n")

    extraction_dir = os.path.join(temp_dir, "extracted")
    os.makedirs(extraction_dir, exist_ok=True)

    summary = "Processing completed."

    try:
        if is_archive_file(file_name):
            extraction_success = await extract_archive(file_path, extraction_dir, update, processing_msg)
            
            if not extraction_success:
                shutil.rmtree(temp_dir)
                return
            
            extracted_files = get_all_files(extraction_dir)
            cookie_files = [f for f in extracted_files if is_valid_file_type(os.path.basename(f))]
            total_files = len(cookie_files)
            
            if total_files == 0:
                await processing_msg.edit_text(
                    "❌ No potential cookie files found in the archive.\n\n"
                    "Make sure your archive contains TXT or JSON cookie files. "
                    "If your archive has nested folders, try organizing the files directly."
                )
                shutil.rmtree(temp_dir)
                return
            
            await processing_msg.edit_text(f"Found {total_files} potential cookie files. Checking...")
            
            for idx, extracted_file in enumerate(cookie_files, 1):
                if idx % 5 == 0:
                    await processing_msg.edit_text(f"Checking: {idx}/{total_files} files...")
                
                file_content, is_text = safe_read_file(extracted_file)
                if not is_text or file_content is None:
                    continue
                
                file_basename = os.path.basename(extracted_file)
                is_json = False
                try:
                    json.loads(file_content)
                    is_json = True
                except json.JSONDecodeError:
                    is_json = False
                except Exception:
                    continue
                
                if check_mode == "spotify":
                    result = await check_spotify_cookie_file(file_content, file_basename, is_json)
                else:  # netflix
                    result = await check_netflix_cookie_file(file_content, file_basename, is_json)
                
                if result["status"] == "valid":
                    results["valid"].append(result)
                    
                    with open(hit_file_path, "a", encoding="utf-8") as hit_file:
                        hit_file.write(f"\n{'='*50}\n")
                        hit_file.write(f"FILE: {file_basename}\n")
                        hit_file.write(f"PATH: {os.path.relpath(extracted_file, extraction_dir)}\n")
                        
                        if check_mode == "spotify":
                            hit_file.write(f"PLAN: {result['plan']}\n")
                            hit_file.write(f"COUNTRY: {result['country']}\n")
                            hit_file.write(f"AUTO-PAY: {result['auto_pay']}\n")
                            hit_file.write(f"TRIAL: {result['trial']}\n")
                        else:  # netflix
                            hit_file.write(f"PLAN: {result['plan']}\n")
                            hit_file.write(f"COUNTRY: {result['country']}\n")
                            hit_file.write(f"MEMBER SINCE: {result['member_since']}\n")
                            hit_file.write(f"MAX STREAMS: {result['max_streams']}\n")
                            hit_file.write(f"EXTRA MEMBERS: {result['extra_members']}\n")
                        
                        hit_file.write(f"{'='*50}\n\n")
                        hit_file.write(result["formatted_content"])
                        hit_file.write("\n\n")
                
                elif result["status"] == "invalid":
                    results["invalid"] += 1
                elif result["status"] == "unsubscribed":
                    results["unsubscribed"] += 1
                else:
                    results["errors"] += 1
        else:
            file_content, is_text = safe_read_file(file_path)
            if not is_text or file_content is None:
                await processing_msg.edit_text(
                    "❌ Your file is not supported. We only accept TXT and ZIP files only.\n\n"
                    "The file you uploaded is not a valid text file. Please make sure you're "
                    "uploading a proper cookie file in text format."
                )
                shutil.rmtree(temp_dir)
                return
            
            is_json = False
            try:
                json.loads(file_content)
                is_json = True
            except json.JSONDecodeError:
                is_json = False
            except Exception:
                await processing_msg.edit_text(
                    "❌ File format not recognized.\n\n"
                    "The file doesn't appear to be a valid cookie file. "
                    "Please make sure you're uploading a proper Netscape or JSON cookie file."
                )
                shutil.rmtree(temp_dir)
                return
            
            if check_mode == "spotify":
                result = await check_spotify_cookie_file(file_content, file_name, is_json)
            else:  # netflix
                result = await check_netflix_cookie_file(file_content, file_name, is_json)
            
            if result["status"] == "valid":
                results["valid"].append(result)
                
                with open(hit_file_path, "a", encoding="utf-8") as hit_file:
                    hit_file.write(f"\n{'='*50}\n")
                    hit_file.write(f"FILE: {file_name}\n")
                    
                    if check_mode == "spotify":
                        hit_file.write(f"PLAN: {result['plan']}\n")
                        hit_file.write(f"COUNTRY: {result['country']}\n")
                        hit_file.write(f"AUTO-PAY: {result['auto_pay']}\n")
                        hit_file.write(f"TRIAL: {result['trial']}\n")
                    else:  # netflix
                        hit_file.write(f"PLAN: {result['plan']}\n")
                        hit_file.write(f"COUNTRY: {result['country']}\n")
                        hit_file.write(f"MEMBER SINCE: {result['member_since']}\n")
                        hit_file.write(f"MAX STREAMS: {result['max_streams']}\n")
                        hit_file.write(f"EXTRA MEMBERS: {result['extra_members']}\n")
                    
                    hit_file.write(f"{'='*50}\n\n")
                    hit_file.write(result["formatted_content"])
            
            elif result["status"] == "invalid":
                results["invalid"] += 1
            elif result["status"] == "unsubscribed":
                results["unsubscribed"] += 1
            else:
                results["errors"] += 1
        
        if len(results["valid"]) == 0 and (results["invalid"] > 0 or results["errors"] > 0 or results["unsubscribed"] > 0):
            summary = (
                f"❌ No valid {check_mode.capitalize()} cookies found.\n\n"
                f"Checked {results['invalid'] + results['errors'] + results['unsubscribed']} files:\n"
                f"- Invalid cookies: {results['invalid']}\n"
                f"- Unsubscribed accounts: {results['unsubscribed']}\n"
                f"- Errors/Skipped: {results['errors']}\n\n"
                f"Make sure you're uploading valid {check_mode.capitalize()} cookies."
            )
        elif sum([len(results["valid"]), results["invalid"], results["errors"], results["unsubscribed"]]) == 0:
            summary = (
                "❌ No cookies were processed.\n\n"
                "Your file may not contain valid cookie data or may have an unsupported format. "
                "Please make sure you're uploading proper cookie files."
            )
        else:
            summary = f"✅ Done! Valid: {len(results['valid'])}, Invalid: {results['invalid']}, Unsubscribed: {results['unsubscribed']}, Errors: {results['errors']}"
        
        await processing_msg.edit_text(summary)
        
        if results["valid"]:
            user = update.effective_user
            user_name = user.first_name
            if user.username:
                user_mention = f"@{user.username}"
            else:
                user_mention = user.first_name
            
            if check_mode == "spotify":
                plans_str, countries_str, autopay_count, trial_count = generate_spotify_stats(results["valid"])
                
                total_processed = len(results["valid"]) + results["invalid"] + results["errors"] + results["unsubscribed"]
                
                caption = (
                    f"🎵 {len(results['valid'])} valid Spotify cookies\n"
                    f"Plans: {plans_str}\n"
                    f"Countries: {countries_str}\n"
                    f"AutoPay: {autopay_count} | Trial: {trial_count}\n\n"
                    f"🔰 Owner: {BOT_OWNER} | 👤 By: {user_mention}\n"
                    f"📢 Channel: {BOT_CHANNEL}"
                )
            else:  # netflix
                plans_str, countries_str, extra_members_count = generate_netflix_stats(results["valid"])
                
                total_processed = len(results["valid"]) + results["invalid"] + results["errors"] + results["unsubscribed"]
                
                caption = (
                    f"🍿 {len(results['valid'])} valid Netflix cookies\n"
                    f"Plans: {plans_str}\n"
                    f"Countries: {countries_str}\n"
                    f"Extra Members: {extra_members_count}\n\n"
                    f"🔰 Owner: {BOT_OWNER} | 👤 By: {user_mention}\n"
                    f"📢 Channel: {BOT_CHANNEL}"
                )
            
            with open(hit_file_path, "rb") as hit_file:
                await update.message.reply_document(
                    document=hit_file,
                    filename=f"{check_mode.capitalize()}_Hit.txt",
                    caption=caption
                )
    
    except Exception as e:
        error_message = f"❌ An error occurred: {str(e)}\n\nPlease try again or contact {BOT_OWNER} for help."
        await processing_msg.edit_text(error_message)
    finally:
        
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    formats = ["TXT files", "Netscape/JSON cookies", "ZIP archives"]
    if HAVE_PY7ZR:
        formats.append("7Z archives")
    if HAVE_RARFILE:
        formats.append("RAR archives")
    
    formats_list = ", ".join(formats)
    
    
    user_id = update.effective_user.id
    is_activated = is_user_activated(user_id)
    activation_status = "✅ Activated" if is_activated else "❌ Not activated"
    
    help_text = (
        f"🔍 Cookie Checker v{BOT_VERSION}\n\n"
        f"Commands:\n"
        f"/start - Start the bot\n"
        f"/help - Show this help\n"
        f"/activate [KEY] - Activate access\n\n"
        f"Supported Formats: {formats_list}\n\n"
        f"How to Use:\n"
        f"1. Select Netflix or Spotify mode\n"
        f"2. Send a cookie file or archive\n"
        f"3. Wait for processing\n"
        f"4. Get results in Hit.txt\n\n"
        f"Bot Info:\n"
        f"• Status: {BOT_STATUS}\n"
        f"• Owner: {BOT_OWNER}\n"
        f"• Channel: {BOT_CHANNEL}\n"
        f"• Developer: {BOT_DEVELOPER}\n"
        f"• Your Status: {activation_status}"
    )
    
    keyboard = [
        [InlineKeyboardButton("Channel", url=f"https://t.me/{BOT_CHANNEL.replace('@', '')}")],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(help_text, reply_markup=reply_markup)



async def cmd_activate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if is_user_activated(user_id):
        await update.message.reply_text("✅ Your account is already activated!")
        return
    
    if not context.args or len(context.args) != 1:
        await update.message.reply_text(
            "⚠️ Please provide a valid key.\n\n"
            "Usage: /activate YOUR_KEY"
        )
        return
    
    key = context.args[0]
    result = activate_user(user_id, key)
    
    if result == True:
        await update.message.reply_text(
            "🎉 Activation successful! You now have access to the bot services.\n\n"
            "Use /start to begin using the bot."
        )
    elif result == "already_activated":
        await update.message.reply_text("✅ Your account is already activated!")
    else:
        await update.message.reply_text(
            "❌ Invalid key! The key may be expired, used up, or doesn't exist.\n\n"
            "Please contact the bot owner for a valid key."
        )

async def cmd_add_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return
    
    if not context.args or len(context.args) < 1 or len(context.args) > 3:
        await update.message.reply_text(
            "⚠️ Invalid format.\n\n"
            "Usage: /addkey KEY [MAX_USES] [EXPIRY_DAYS]\n"
            "Example: /addkey ABC123 5 30"
        )
        return
    
    key = context.args[0]
    max_uses = int(context.args[1]) if len(context.args) > 1 else 1
    expiry_days = int(context.args[2]) if len(context.args) > 2 else 30
    
    result = add_key(key, max_uses, expiry_days, f"admin_{user_id}")
    
    if result:
        await update.message.reply_text(
            f"✅ Key added successfully!\n\n"
            f"Key: `{key}`\n"
            f"Max Uses: {max_uses}\n"
            f"Expires in: {expiry_days} days"
        )
    else:
        await update.message.reply_text("❌ Failed to add key. The key might already exist.")

async def cmd_delete_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return
    
    if not context.args or len(context.args) != 1:
        await update.message.reply_text(
            "⚠️ Please provide a key to delete.\n\n"
            "Usage: /delkey KEY"
        )
        return
    
    key = context.args[0]
    result = delete_key(key)
    
    if result:
        await update.message.reply_text(f"✅ Key `{key}` has been deleted.")
    else:
        await update.message.reply_text(f"❌ Key `{key}` not found.")

async def cmd_list_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return
    
    keys = get_all_keys()
    
    if not keys:
        await update.message.reply_text("No keys found in the database.")
        return
    
    message = "🔑 Available Keys:\n\n"
    for key, created_date, expiry_date, max_uses, uses, created_by in keys:
        message += f"Key: `{key}`\n"
        message += f"Created: {created_date}\n"
        message += f"Expires: {expiry_date}\n"
        message += f"Uses: {uses}/{max_uses}\n"
        message += f"Created by: {created_by}\n\n"
    
    await update.message.reply_text(message)

async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return
    
    conn = sqlite3.connect('bot_keys.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT user_id, key, activated_date, expiry_date FROM activated_users")
    users = cursor.fetchall()
    
    conn.close()
    
    if not users:
        await update.message.reply_text("No activated users found.")
        return
    
    message = "👥 Activated Users:\n\n"
    for user_id, key, activated_date, expiry_date in users:
        message += f"User ID: {user_id}\n"
        message += f"Key: {key}\n"
        message += f"Activated: {activated_date}\n"
        message += f"Expires: {expiry_date}\n\n"
    
    await update.message.reply_text(message)



def print_startup_banner():
    try:
        os.system('cls' if os.name == 'nt' else 'clear')
    except:
        print("\n" * 5)
    
    banner = f""" 🍿 NETFLIX & SPOTIFY COOKIE CHECKER BOT v{BOT_VERSION} 🎵
    
    Owner: {BOT_OWNER}
    Channel: {BOT_CHANNEL}
    Developed by: {BOT_DEVELOPER}
    Status: {BOT_STATUS}
    Supported formats: {"ZIP" + ("/7Z" if HAVE_PY7ZR else "") + ("/RAR" if HAVE_RARFILE else "")}
    
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║  Bot is now running with key system! Press Ctrl+C to stop.    ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    print(banner)

def main():
    
    os.makedirs("spotify_hits", exist_ok=True)
    os.makedirs("netflix_hits", exist_ok=True)
    os.makedirs("failures", exist_ok=True)
    os.makedirs("broken", exist_ok=True)
    os.makedirs("free", exist_ok=True)
    os.makedirs("converted", exist_ok=True)
    
    
    setup_database()
    
    print_startup_banner()
    
    application = Application.builder().token("8098505872:AAG1AcpYfjd5W1r9BnqTppZBVynZUT5azQ0").build()
    
    
    application.add_handler(CommandHandler("activate", cmd_activate))
    application.add_handler(CommandHandler("addkey", cmd_add_key))
    application.add_handler(CommandHandler("delkey", cmd_delete_key))
    application.add_handler(CommandHandler("listkeys", cmd_list_keys))
    application.add_handler(CommandHandler("users", cmd_users))
    
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    
   
    application.add_handler(MessageHandler(filters.Document.ALL, process_file))
    
    async def error_handler(update, context):
        print(f"Error occurred: {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text(
                f"An error occurred. Please try again or contact {BOT_OWNER} for help."
            )
    
    application.add_error_handler(error_handler)
    
    current_time = time.strftime("%H:%M:%S", time.localtime())
    print(f"[{current_time}] Bot started successfully with key system!")
    print(f"[{current_time}] Admin ID set: {ADMIN_ID}")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
