import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
import os
import random
import subprocess
from dotenv import load_dotenv


# Initialize the bot with intents and a new command prefix
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="_music ", intents=intents)

song_queue = []  # Global queue to store song URLs

# Notify when the bot is ready
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print(f"Bot is connected to {len(bot.guilds)} servers.")
    print("Bot is ready to receive commands!")

# Simple test command to check bot's response
@bot.command()
async def test(ctx):
    await ctx.send("Bot is online and responding!")

# Join voice channel command
@bot.command()
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        if not ctx.voice_client or not ctx.voice_client.is_connected():
            await channel.connect()
            await ctx.send(f"Successfully joined the voice channel: {channel.name}")
        else:
            await ctx.send("Already connected to a voice channel!")
    else:
        await ctx.send("You need to be in a voice channel first!")

# Leave voice channel command
@bot.command()
async def leave(ctx):
    if ctx.voice_client and ctx.voice_client.is_connected():
        await ctx.voice_client.disconnect()
        await ctx.send("Disconnected from the voice channel.")
    else:
        await ctx.send("I'm not connected to any voice channel.")

# Play YouTube audio with enhanced queue management (support for playlists)
@bot.command()
async def play(ctx, url):
    global song_queue
    if not ctx.voice_client:
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            await channel.connect()
        else:
            await ctx.send("Join a voice channel first!")
            return

    # Function to play the next song in the queue
    async def play_next(ctx):
        if song_queue:
            next_url = song_queue.pop(0)
            try:
                # Enhanced download options
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'quiet': True,
                    'noplaylist': True,
                    'source_address': '0.0.0.0',
                }

                with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(next_url, download=False)
                    audio_url = info['url']

                # Enhanced FFmpeg options for better streaming
                source = await discord.FFmpegOpusAudio.from_probe(
                    audio_url,
                    before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                    options='-vn'
                )

                def after_playing(error):
                    if error:
                        print(f"Error in playback: {error}")
                    bot.loop.create_task(play_next(ctx))

                ctx.voice_client.play(source, after=after_playing)
                await ctx.send(f"Now playing: {info['title']}")
            except Exception as e:
                await ctx.send(f"Error playing {next_url}: {e}")
                # Continue to the next song if this one fails
                await play_next(ctx)

    # Check if the URL is a playlist
    if "list=" in url:
        # Extract all the videos in the playlist
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,  # This will only extract video URLs without downloading
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            playlist_info = ydl.extract_info(url, download=False)
            if 'entries' in playlist_info:
                for entry in playlist_info['entries']:
                    song_queue.append(entry['url'])
                await ctx.send(f"Added {len(playlist_info['entries'])} songs from the playlist to the queue.")
            else:
                await ctx.send("Could not extract playlist information.")
    elif "watch?v=" in url and "list=" in url:
        # Video URL with a playlist (watch?v=ID&list=ID)
        playlist_id = url.split('list=')[-1]
        playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"

        # Extract the songs from the playlist
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,  # Extract video URLs without downloading
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            playlist_info = ydl.extract_info(playlist_url, download=False)
            if 'entries' in playlist_info:
                for entry in playlist_info['entries']:
                    song_queue.append(entry['url'])
                await ctx.send(f"Added {len(playlist_info['entries'])} songs from the playlist to the queue.")
            else:
                await ctx.send("Could not extract playlist information.")
    else:
        # Single video URL
        song_queue.append(url)
        await ctx.send(f"Added to queue: {url}")

    # Only start playing if not already playing
    if not ctx.voice_client.is_playing():
        await play_next(ctx)

# Skip the current song
@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Skipped the current song!")
    else:
        await ctx.send("No song is currently playing.")

# Display the current queue
@bot.command(name="queue")
async def show_queue(ctx):
    if song_queue:
        # Create the message in chunks to avoid exceeding 4000 characters
        message = ""
        for i, url in enumerate(song_queue):
            message += f"{i+1}. {url}\n"
            # If message length exceeds 2000 characters, send and reset it
            if len(message) > 2000:
                await ctx.send(f"Current queue:\n{message}")
                message = ""  # Reset the message
        
        if message:  # Send any remaining part of the message
            await ctx.send(f"Current queue:\n{message}")
    else:
        await ctx.send("The queue is empty!")

# Show the currently playing song
@bot.command()
async def now_playing(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        current_url = song_queue[0]
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(current_url, download=False)
            await ctx.send(f"Now playing: {info['title']}")
    else:
        await ctx.send("No song is currently playing.")

# Pause the current song
@bot.command()
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Paused the current song.")
    else:
        await ctx.send("No song is currently playing.")

# Resume the current song
@bot.command()
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Resumed the song.")
    else:
        await ctx.send("No song is paused.")

# Clear the entire song queue
@bot.command()
async def clear(ctx):
    global song_queue
    song_queue = []
    await ctx.send("Cleared the song queue.")

# Shuffle the song queue
@bot.command()
async def shuffle(ctx):
    global song_queue
    random.shuffle(song_queue)
    await ctx.send("Shuffled the song queue.")

# Loop the current song
@bot.command()
async def loop(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        current_url = song_queue[0]  # Get the current song URL
        song_queue.append(current_url)  # Add it back to the queue for looping
        await ctx.send("The current song will loop.")
    else:
        await ctx.send("No song is currently playing.")

# Skip to a specific song in the queue
@bot.command()
async def skip_to(ctx, song_number: int):
    if 1 <= song_number <= len(song_queue):
        song_url = song_queue[song_number - 1]
        song_queue = song_queue[song_number:]  # Remove all songs before the selected song
        await ctx.send(f"Skipping to song: {song_url}")
        await play_next(ctx)  # Start playing the song from the new position
    else:
        await ctx.send("Invalid song number.")

# Check if the bot has permissions
@bot.command()
async def check_permissions(ctx):
    permissions = ctx.guild.me.guild_permissions
    required_permissions = ['connect', 'speak']
    missing = [perm for perm in required_permissions if not getattr(permissions, perm, False)]
    
    if not missing:
        await ctx.send("The bot has all necessary permissions.")
    else:
        await ctx.send(f"The bot is missing the following permissions: {', '.join(missing)}")

# FFmpeg Check Command
@bot.command()
async def ffmpeg_check(ctx):
    try:
        # Try to run FFmpeg and capture its version
        result = subprocess.run(['ffmpeg', '-version'], 
                                capture_output=True, 
                                text=True, 
                                timeout=5)
        
        if result.returncode == 0:
            # Extract the version information
            version_line = result.stdout.split('\n')[0]
            await ctx.send(f"FFmpeg is installed. Version info:\n{version_line}")
        else:
            await ctx.send("FFmpeg is installed but returned an error.")
    except FileNotFoundError:
        await ctx.send("FFmpeg is NOT installed or not in system PATH.")
    except subprocess.TimeoutExpired:
        await ctx.send("FFmpeg check timed out.")
    except Exception as e:
        await ctx.send(f"An error occurred while checking FFmpeg: {e}")


load_dotenv()  # Make sure this is called before accessing the token
BOT_TOKEN = os.getenv("DISCORD_TOKEN")

if not BOT_TOKEN:
    print("Error: DISCORD_TOKEN is not found!")
    exit(1)  # Exit if no token is found

bot.run(BOT_TOKEN)
