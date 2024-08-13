import telebot
import os
from dotenv import load_dotenv
import requests
import subprocess
from telebot import types
import hashlib
import time
import json
from google.cloud import secretmanager
from flask import Flask, request, abort



def get_access_token():
    # Get the access token using gcloud command
    access_token = subprocess.check_output(
        ["gcloud", "auth", "print-access-token"]
    ).decode("utf-8").strip()
    return access_token

def get_secret_value(project_id, secret_id, version_id="latest"):
    # Construct the API URL
    url = f"https://secretmanager.googleapis.com/v1/projects/{project_id}/secrets/{secret_id}/versions/{version_id}:access"

    # Get the access token
    token = get_access_token()

    # Set the headers
    headers = {
        "authorization": f"Bearer {token}",
        "content-type": "application/json",
    }

    # Send the GET request to the Secret Manager API
    response = requests.get(url, headers=headers)

    # Check if the request was successful
    if response.status_code == 200:
        # Extract the secret payload
        secret_data = response.json()["payload"]["data"]
        return secret_data
    else:
        # Handle error
        raise Exception(f"Failed to access secret: {response.text}")

# Replace these variables with your specific details
project_id = "279037284563"
secret_id = "TELEGRAM_BOT_TOKEN"
version_id = "1"  # or a specific version number, e.g., "1"

# Get the secret value
secret_value = get_secret_value(project_id, secret_id, version_id)

# Decode the secret from Base64
import base64
TOKEN = base64.b64decode(secret_value).decode("utf-8")




if not TOKEN:
    raise Exception("TELEGRAM_BOT_TOKEN is not set in the environment variables")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Cobalt API endpoint
COBALT_API_URL = 'https://api.cobalt.tools/api/json'

# Dictionary to store user states and download links
user_states = {}
download_links = {}

# Load supported domains from JSON file
with open('supported_domains.json', 'r') as f:
    supported_domains = json.load(f)['domains']

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_message = (
        "👋 *Welcome to the Video Download Bot!*\n\n"
        "I'm here to help you download videos from various platforms. Just send me a video URL, and I'll extract the download link for you.\n\n"
        "📌 *Supported Domains:*\n"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(domain['name'], callback_data=domain['callback_data']) for domain in supported_domains]
    markup.add(*buttons)

    usage_instructions = (
        "\n🔗 *How to Use:*\n"
        "1. Send me a video URL from one of the supported domains.\n"
        "2. I'll provide you with a download link.\n"
        "3. Confirm if you want to download in this chat.\n\n"
        "Happy downloading! 🚀"
    )

    bot.reply_to(message, welcome_message + usage_instructions, parse_mode='Markdown', reply_markup=markup)
    print(f"Received /start command from user: {message.from_user.username}")  # Debugging line

def is_valid_url(url):
    # Add your URL validation logic here
    return True

# Function to call the Cobalt API and get the download link
def call_api(url):
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    data = {
        'url': url
    }
    print(f"Making API call with headers: {headers} and body: {data}")  # Debugging line
    response = requests.post(COBALT_API_URL, headers=headers, json=data)
    print(f"API response status: {response.status_code}, body: {response.json()}")  # Debugging line
    return response.json()

# Function to download the video from the download link
def download_video(download_link):
    response = requests.get(download_link, stream=True)
    file_name = "downloaded_video.mp4"
    with open(file_name, 'wb') as video_file:
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                video_file.write(chunk)
    return file_name

# Message handler for URLs
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    print(f"Received message: {message.text} from user: {message.from_user.username}")  # Debugging line

    if user_id in user_states and user_states[user_id]['state'] == 'awaiting_confirmation':
        # This block is no longer needed as we will handle button presses in a callback query handler
        pass
    else:
        if is_valid_url(message.text):
            processing_message = bot.reply_to(message, "Processing your URL...")
            print(f"Processing URL: {message.text}")  # Debugging line
            try:
                api_response = call_api(message.text)
                status = api_response.get('status')
                download_link = api_response.get('url')

                # Delete the "Processing your URL..." message
                bot.delete_message(chat_id=processing_message.chat.id, message_id=processing_message.message_id)

                if status == 'redirect' and download_link:
                    # Treat redirected URL as the download link
                    bot.reply_to(message, f"Redirected URL: {download_link}\nUsing the redirected URL as the download link.")
                    print(f"Redirected URL: {download_link}")  # Debugging line

                if download_link:
                    # Generate a short identifier for the download link
                    link_id = hashlib.md5(download_link.encode()).hexdigest()[:10]
                    download_links[link_id] = download_link

                    markup = types.InlineKeyboardMarkup()
                    yes_button = types.InlineKeyboardButton("✅ Yes", callback_data=f"download:{link_id}")
                    no_button = types.InlineKeyboardButton("❌ No", callback_data="cancel")
                    markup.add(yes_button, no_button)
                    bot.reply_to(message, f"Download Link: {download_link}\nDo you want to download the video?", reply_markup=markup)
                    user_states[user_id] = {'state': 'awaiting_confirmation', 'download_link': download_link}
                else:
                    bot.reply_to(message, "Failed to retrieve download link.")
            except Exception as e:
                bot.reply_to(message, f"Failed to process the URL: {str(e)}")
                print(f"Failed to process the URL: {str(e)}")  # Debugging line
                if user_id in user_states:
                    del user_states[user_id]  # Clear the user state on error
        else:
            bot.reply_to(message, "Invalid URL. Please send a valid video URL.")
            print(f"Invalid URL received: {message.text}")  # Debugging line
            
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    if call.data.startswith("download:"):
        link_id = call.data.split("download:")[1]
        download_link = download_links.get(link_id)
        if download_link:
            # Answer the callback query immediately
            bot.answer_callback_query(call.id)

            try:
                # Edit the message to show "Downloading" with an emoji
                markup = types.InlineKeyboardMarkup()
                downloading_button = types.InlineKeyboardButton("⬇️ Downloading", callback_data="noop")
                markup.add(downloading_button)
                bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)

                file_path = download_video(download_link)
                with open(file_path, 'rb') as video:
                    bot.send_video(call.message.chat.id, video)
                os.remove(file_path)  # Clean up the downloaded file
            except telebot.apihelper.ApiException as e:
                if e.result.status_code == 413:
                    bot.send_message(call.message.chat.id, "Failed to download the video: The video is too large to send via Telegram.")
                else:
                    bot.send_message(call.message.chat.id, f"Failed to download the video: {str(e)}")
                print(f"Failed to download the video: {str(e)}")  # Debugging line
            except Exception as e:
                bot.send_message(call.message.chat.id, f"Failed to download the video: {str(e)}")
                print(f"Failed to download the video: {str(e)}")  # Debugging line
            finally:
                if user_id in user_states:
                    del user_states[user_id]  # Clear the user state after processing
        else:
            bot.send_message(call.message.chat.id, "Invalid download link.")
    elif call.data == "cancel":
        bot.answer_callback_query(call.id)  # Acknowledge the callback query
        bot.send_message(call.message.chat.id, "Okay, not downloading the video.")
    else:
        bot.answer_callback_query(call.id)  # Acknowledge the callback query
    if user_id in user_states:
        del user_states[user_id]  # Clear the user state

@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_str = request.get_data().decode('UTF-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return '', 200
    else:
        abort(403)

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL + TOKEN)
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
