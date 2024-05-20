import asyncio
from threading import Thread
import os
import discord
from discord.ext import commands
import streamlit as st

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, allowed_mentions=discord.AllowedMentions.none())

@bot.event
async def on_ready():
    print("Bot is ready!")

@bot.event
async def on_message(message):
    if message.author == bot.user or message.author.bot:
        return

    mentioned = bot.user.mentioned_in(message)
    is_reply = message.reference and message.reference.resolved.author == bot.user

    if not (mentioned or is_reply):
        return

    await message.reply("Hello! I'm Aquarius, your AI assistant!", mention_author=False)

@bot.slash_command(name="reset", description="Reset the chat history")
async def reset(ctx):
    embed = discord.Embed(
        title="Reset",
        description="My memory has been reset and I'm ready for a fresh conversation.",
        color=0x00B3FF
    )
    await ctx.respond(embed=embed, ephemeral=True)

@bot.slash_command(name="help", description="A guide to using Aquarius")
async def help(ctx):
    embed = discord.Embed(
        title="Help",
        description="I'm Aquarius, your AI assistant!",
        color=0x00B3FF
    )
    embed.add_field(name="Features", value="Image Analysis\nMulti-Turn Conversations\nWeb Search", inline=False)
    embed.add_field(name="How to Chat", value="Mention me or reply to my messages\n", inline=False)
    embed.add_field(name="Commands",
                    value="/reset - Clear the chat history\n/help - See this message\n/donate - Support Aquarius's development\n/settings - Configure the settings of Aquarius",
                    inline=False)
    await ctx.respond(embed=embed)

@bot.slash_command(name="donate", description="Support Aquarius")
async def donate(ctx):
    embed = discord.Embed(
        title="Donate",
        description="Your support helps us improve and maintain Aquarius. Every contribution is greatly appreciated!",
        color=0x00B3FF
    )
    embed.add_field(
        name="Payment Methods", value="[Kofi](https://ko-fi.com/wwize)"
    )
    await ctx.respond(embed=embed)

@bot.slash_command(name="settings", description="Configure Aquarius")
async def settings(ctx, websearch: bool):
    embed = discord.Embed(title="Settings", color=0x00B3FF)

    if websearch:
        embed.description = "Web search is now enabled. I will use web search results to enhance my responses and provide you with the most up-to-date information."
    else:
        embed.description = "Web search is now disabled. I will rely solely on my internal knowledge base to respond to your queries."

    await ctx.respond(embed=embed, ephemeral=True)

async def bot_main():
    await bot.start(os.getenv('DISCORD_BOT_TOKEN'))

def start_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(bot_main())

def streamlit_app():
    st.write("Hello, World!")

if __name__ == '__main__':
    bot_thread = Thread(target=start_bot)
    bot_thread.start()

    thread = Thread(target=streamlit_app)
    thread.start()
    streamlit_app()