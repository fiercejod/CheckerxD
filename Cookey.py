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
        start_message += "\n\n✅ Your account is activated!
