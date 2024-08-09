import asyncio
from playwright.async_api import async_playwright
import telebot
import json
import os

# Initialize the bot with your token
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)

# Cobalt API endpoint
COBALT_API_URL = 'https://api.cobalt.tools/api/json'

# Start command handler
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Hi! Send me a video URL, and I will extract the download link for you.")

# Function to validate supported URLs
def is_supported_url(url):
    supported_domains = ['youtube.com', 'youtu.be', 'tiktok.com']
    return any(domain in url for domain in supported_domains)

# Playwright function to handle the API request
async def fetch_video_link(url, payload):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # Attempt to directly make the request using the same setup as Postman
            response = await page.request.post(
                url,
                headers={
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                },
                data=json.dumps(payload)
            )

            # Log the response content
            response_text = await response.text()
            print("Raw Response Content:", response_text)

            # Check the response status
            if response.status != 200:
                return {"error": f"Failed with status code {response.status}"}

            # Attempt to parse the response as JSON
            try:
                response_data = json.loads(response_text)
                return response_data
            except json.JSONDecodeError:
                return {"error": "Response was not valid JSON"}

        except Exception as e:
            print(f"An error occurred: {str(e)}")
            return {"error": str(e)}

        finally:
            await browser.close()

# Handler for text messages
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url = message.text.strip()

    if not is_supported_url(url):
        bot.reply_to(message, "The provided URL is not supported by the Cobalt API. Please send a URL from supported platforms like YouTube or TikTok.")
        return

    # Construct the payload according to the API documentation
    payload = {
        'url': url,
        'vCodec': 'h264',
        'vQuality': '720',
        'aFormat': 'mp3',
        'disableMetadata': True
    }

    # Use Playwright to fetch the video link
    response = asyncio.run(fetch_video_link(COBALT_API_URL, payload))

    if 'error' in response:
        bot.reply_to(message, f"Failed to fetch video link: {response['error']}")
    elif response.get('status') == 'success':
        video_url = response.get('url')
        bot.reply_to(message, f"Here is your download link: {video_url}")
    else:
        error_text = response.get('text', 'Unknown error')
        bot.reply_to(message, f"Failed to extract video: {error_text}")

# Polling to continuously check for new messages
bot.polling()
