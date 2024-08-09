import telebot
import os
from dotenv import load_dotenv
from pytube import YouTube
from pytube.exceptions import VideoUnavailable, PytubeError

load_dotenv()

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
print(f"Loaded TOKEN: {TOKEN}")  # Debugging line

if not TOKEN:
    raise Exception("TELEGRAM_BOT_TOKEN is not set in the environment variables")

bot = telebot.TeleBot(TOKEN)

# Start command handler
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Hi! Send me a YouTube video URL, and I will download the video for you.")
    print(f"Received /start command from user: {message.from_user.username}")  # Debugging line

# Function to validate YouTube URLs
def is_valid_youtube_url(url):
    return "youtube.com" in url or "youtu.be" in url

# Function to download video and send it back to the user
def download_video(url):
    try:
        yt = YouTube(url)
        stream = yt.streams.filter(progressive=True, file_extension='mp4').first()
        if not stream:
            raise Exception("No suitable stream found.")
        file_path = stream.download()
        return file_path
    except VideoUnavailable:
        raise Exception("The video is unavailable.")
    except PytubeError as e:
        raise Exception(f"Pytube error occurred: {str(e)}")
    except Exception as e:
        raise Exception(f"An error occurred: {str(e)}")

# Message handler for URLs
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    print(f"Received message: {message.text} from user: {message.from_user.username}")  # Debugging line
    if is_valid_youtube_url(message.text):
        bot.reply_to(message, "Processing your URL...")
        print(f"Processing URL: {message.text}")  # Debugging line
        try:
            file_path = download_video(message.text)
            with open(file_path, 'rb') as video:
                bot.send_video(message.chat.id, video)
            os.remove(file_path)  # Clean up the downloaded file
        except Exception as e:
            bot.reply_to(message, f"Failed to download video: {str(e)}")
            print(f"Failed to download video: {str(e)}")  # Debugging line
    else:
        bot.reply_to(message, "Invalid URL. Please send a valid YouTube video URL.")
        print(f"Invalid URL received: {message.text}")  # Debugging line

if __name__ == "__main__":
    print("Bot is polling...")  # Debugging line
    bot.polling()