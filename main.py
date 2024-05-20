import os
import google.generativeai as genai
from discord import Activity, ActivityType, CustomActivity, Embed
import discord
from discord.ext import commands, tasks
import asyncio
import random
import json
import base64
import io
from PIL import Image
from io import BytesIO
from threading import Thread
from bs4 import BeautifulSoup
import concurrent.futures
from duckduckgo_search import DDGS
import aiohttp
import gc
import time
import datetime
from dotenv import load_dotenv
import os

load_dotenv()


genai.configure(api_key='AIzaSyDp8wSYfJmihGPmW6g18flUojJmEhEmQ5M')

text_model = genai.GenerativeModel('gemini-pro')
image_model = genai.GenerativeModel('gemini-pro-vision')
user_chats = {}
user_settings = {}

text_generation_model = genai.GenerativeModel('gemini-pro')

generation_config = {
    "temperature": 0.7,
    "top_p": 1,
    "top_k": 32,
    "max_output_tokens": 4096,
}

safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE"
    }
]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, allowed_mentions=discord.AllowedMentions.none())
second_image_model = genai.GenerativeModel('gemini-pro-vision')


def generate_search_query(query, user_id):
    """
    This function generates a search query based on the user's input and context.
    It uses a prompt to instruct the text generation model to create a relevant query
    for DuckDuckGo search, taking into account the user's previous queries and the
    bot's knowledge cutoff date.
    """
    current_time = datetime.datetime.now(datetime.timezone.utc)
    date_string = current_time.strftime("%a, %d %b %Y, %H:%M:%S UTC")
    prompt = f"""
    input: {query}
 
## Additional Context
- The date and time is {date_string}.

## You are a query generation system designed solely to provide relevant search queries based on the user's input. If the input does not require up-to-date information or refers to something beyond your knowledge base, you may generate 1-3 focused search queries separated by newlines when needed. Your knowledge cutoff date is August 2023.

## If the input is a casual conversation, a statement, an opinion, a thank you message, or any other input that does not require a factual search query response, you must respond with "c". Do not attempt to engage in conversation or provide any other responses.

## However, if the input is a factual query requiring the most current information, data that may have changed since August 2023, or something unfamiliar to you, you may generate 1-3 concise and focused Google search queries separated by newlines to retrieve relevant up-to-date information when a single query is insufficient.

## Generate multiple queries only if the question is complex and broad, requiring additional context or perspectives for a comprehensive answer. For simple factual queries, a single focused query should suffice.

## When generating search queries, strictly adhere to these guidelines:

- Use a Colon to Search Specific Sites:
To find content on a particular website, use this syntax: "Sidney Crosby site:nhl.com". This will search for articles about hockey player Sidney Crosby, but only on NHL.com, excluding other search results. Use this technique when you need specific content from a certain site.

- Keep it Simple:
Google search is intelligent, so you don't need to be overly specific. For example, to find nearby pizza places, use: "Pizza places near me"

- Use Professional WebsiteTerminology:
Websites often use formal language, unlike casual speech. For better results, use terms found on professional websites. For example:
- Instead of "I have a flat tire", use "repair a flat tire".
- Instead of "My head hurts", use "headache remedies".

- Use Important Keywords Only:
Google search is intelligent, so you don't need to be overly specific. Using too many words may limit results and make it harder to find what you need. Use only the most important keywords when searching. For example:
- Don't use: "Where can I find a Chinese restaurant that delivers?"
- Instead, try: "Chinese takeout near me"

- Use Descriptive Words:
Things can be described in multiple ways. If you struggle to find what you're searching for, rephrase the query using different descriptive words. For example, instead of "How to install drivers in Ubuntu?", try "Ubuntu driver installation troubleshooting".

- Searching For Related Websites:
If you want to find a website that is similar or related to a specific website, you can do this by entering related:website.com.

- Find Specific Files;
To search for a specific file or file type, use the "filetype" operator:
*Search term here* filetype:pdf
Replace "search term here" with your query and specify the file extension (pdf, ppt, etc.) after "filetype:".

- Use Quotations for Exact Phrases:
Searching for Patrick Stewart young will return results containing those words, but not necessarily in that order. By enclosing the phrase in quotations, like "Patrick Stewart young", you will only get results with those exact words in that sequence.

## You are strictly a query generation system. You do not engage in conversation or provide any other responses besides outputting focused search queries or "c". You have no additional capabilities.

Input: can you help me study
Output: c
Input: find me open-source projects
Output: open source related:github.com
Input: Best ways to save money on groceries
Output: grocery saving tips\ncoupons for grocery stores\n"frugal living" site:reddit.com/r/Frugal
Input: What is the weather forecast for tomorrow in San Francisco?
Output: san francisco weather forecast
Input: How can I learn to code in Python?
Output: python programming tutorials for beginners\npython programming
learn python coding
Input: Thank you for your help!
Output: c
Input: Tell me a joke.
Output: c
Input: What are some healthy dinner recipes?
Output: healthy dinner recipes\neasy healthy meals
Input: I want to buy a new laptop, what are the best options in 2024?
Output: best laptops 2024\nlaptop reviews 2024\ntop rated laptops april 2024
Input: Can you recommend a good plumber in Chicago?
Output: chicago plumbers\nplumbing services chicago\ntop rated plumbers chicago
Input: How do I install the latest graphics drivers for my NVIDIA GPU on Ubuntu 22.04?
Output: install nvidia graphics drivers ubuntu 22.04\nubuntu 22.04 nvidia driver installation
Input: PDF version of the UN Climate Report 2024
Output: un climate report 2023 filetype:pdf"""
    generation_config = {
        "temperature": 0.7,
        "top_p": 1,
        "top_k": 32,
        "max_output_tokens": 4096,
    }
    response = user_chats[user_id]["text_generation_chat"].send_message(
        content=prompt, generation_config=generation_config, safety_settings=safety_settings
    )

    if response.text.strip().lower() == "c":
        return "CANCEL_WEBSEARCH"
    else:
        generated_query = response.text.strip()
        print(f"Using search query: {generated_query}")
        return generated_query


async def scrape_and_process_results(queries, max_results_per_query):
    """
    This function scrapes and processes information from DuckDuckGo search results
    for multiple queries and returns the results in JSON format.
    It dynamically adjusts based on the provided max_results_per_query.
    Error handling for individual URLs is removed.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0"
    }
    all_results_json = []
    async with aiohttp.ClientSession() as session:
        for query_idx, query in enumerate(queries):
            ddg = DDGS(headers=headers)
            search_results = ddg.text(query, max_results=max_results_per_query, safesearch="on")

            results_json = []
            for idx, result in enumerate(search_results, start=1):
                if len(results_json) >= max_results_per_query:
                    break
                url = result['href']
                name = result['title']

                text_content = await process_url(url, session)  # No error handling here
                results_json.append({
                    "index": idx,
                    "url": url,
                    "name": name,
                    "content": text_content
                })

            all_results_json.append(results_json)

    return json.dumps(all_results_json) 


async def process_url(url, session):
    """
    This function processes a given URL by fetching its HTML content and extracting
    relevant text from paragraphs (p), headings (h1, h2) using BeautifulSoup.
    """
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            html_content = await response.text()
            soup = BeautifulSoup(html_content, "lxml")
            relevant_text = ' '.join([tag.get_text() for tag in soup.find_all(['p', 'h1', 'h2'])])
            return relevant_text
    except Exception as e:
        print(f"Error processing URL {url}: {e}")
        return ''


@bot.event
async def on_message(message):
    if message.author == bot.user or message.author.bot:
        return

    mentioned = bot.user.mentioned_in(message)
    is_reply = message.reference and message.reference.resolved.author == bot.user

    if not (mentioned or is_reply):
        return

    user = message.author
    user_id = message.author.id

    if message.guild is not None:
        guild = message.guild
        guild_name = guild.name
        channel = message.channel
        channel_name = channel.name
        print(
            f"Nickname: {user.name}\nServer Name: {guild_name}\nChannel: {channel_name}\nPrompt: {message.content}\n")
    else:
        print(f"Sent in DMs\nUser: {user.name}\nPrompt: {message.content}\n")

    try:
        user = message.author
        user_id = message.author.id

        if user_id not in user_chats:
            user_chats[user_id] = {
                "text_model_chat": text_model.start_chat(history=[]),
                "text_generation_chat": text_generation_model.start_chat(history=[]),
                "is_busy": False  # Initialize busy flag
            }
            user_settings[user_id] = {"websearch": True, "stream": True}
  # Set default se}  # Set default settings

        user_text_chat = user_chats[user_id]["text_model_chat"]
        user_generation_chat = user_chats[user_id]["text_generation_chat"]

        # Check if bot is busy
        if user_chats[user_id].get("is_busy", False):
            return  # Ignore message if bot is busy

        # Set busy flag before processing
        user_chats[user_id]["is_busy"] = True

        if bot.user.mention in message.content or message.reference:
            user_input = message.content.replace(bot.user.mention, "").strip() if bot.user.mention in message.content else message.content.strip()

            async with message.channel.typing():

                if user_settings.get(user_id, {}).get("websearch", True):

                    generated_query = generate_search_query(user_input, user_id)

                    if generated_query != "CANCEL_WEBSEARCH":
                        queries = generated_query.strip().split('\n')
                        searching_messages = []  # Store messages to delete later
                        for q in queries:
                            searching_message = await message.channel.send(f"<a:emoji_7:1234741363552288768> {q}")
                            searching_messages.append(searching_message)

                if message.attachments:
                    image_parts = []

                    for attachment in message.attachments:
                        image_data = await attachment.read()
                        image_mime = attachment.content_type
                        image_parts.append({
                            "mime_type": image_mime,
                            "data": image_data
                        })

                    prompt_parts = image_parts + [user_input]

                    response = image_model.generate_content(prompt_parts, generation_config=generation_config,
                                                           safety_settings=safety_settings, stream=True)

                    second_prompt_parts = image_parts + [
                        """## For the provided image, I'd like you to analyze and describe every single visual element and detail that you can detect. Please go through the image systematically, describing objects, people, scenes, text, colors, textures, patterns, and any other noteworthy aspects with an extremely high level of granularity.

## Start by providing an overall high-level summary of the main subjects and contents of the image. Then, section by section, describe the finer components - shapes, sizes, positions, orientations, anything that can be articulated about what is pictured. For complex scenes, break it down into foreground, background, individual elements, etc.

## If you see text or numbers, transcribe them verbatim. Note any branding, logos, or potentially identifiable details. Describe materials, surfaces, lighting, and shadow details to the extent possible. Leave no stone unturned in exhaustively listing out and describing the visual information contained in this image down to the pixel level if needed.
The goal is to provide a text description so overwhelmingly complete that anyone reading it could re-create or vividly imagine the original image in their mind's eye from your words alone. Be as thorough and comprehensive as possible in annotating absolutely everything you perceive in the provided image."""]
                    second_response = second_image_model.generate_content(second_prompt_parts,
                                                                          generation_config=generation_config,
                                                                          safety_settings=safety_settings)

                    secondvisionresponse = second_response.text

                    initial_message = await message.reply("<a:emoji_5:1234056677725311077>", mention_author=False)
                    await asyncio.sleep(1)
                    full_response = ""
                    for chunk in response:
                    	full_response += chunk.text
                    	await initial_message.edit(content=full_response)
                    	await asyncio.sleep(0)

                    user_text_chat.history.append({
                        "role": "user",
                        "parts": [{"text": user_input}]
                    })
                    user_text_chat.history.append({
                        "role": "model",
                        "parts": [
                            {"text": "Only send the short details. Never give out the full details unless said so.\n[system](#full_image_details)\n" + secondvisionresponse + "[system](#short_image_details)\n" + response.text}]
                    })

                else:
                    
                    scraped_results_json = ""
                    if user_settings.get(user_id, {}).get("websearch", True) and generated_query != "CANCEL_WEBSEARCH":
                        max_results_per_query = 3 # Replace with desired max results or a dynamic value
                        queries = generated_query.strip().split('\n') 
                        scraped_results_json = await scrape_and_process_results(queries, max_results_per_query)

                        if message.guild is not None:
                            current_time = datetime.datetime.now(datetime.timezone.utc)
                            date_string = current_time.strftime("%a, %d %b %Y, %H:%M:%S UTC")

                            user_name = user.name
                            response = user_text_chat.send_message(f"""{user_input}

## Additional Context
- New conversation with {user_name}
- The date and time is {date_string}.
- Websearch is enabled.

## You are a large language model trained by Aquarius AI. Write an accurate answer concisely for a given question, always citing the search results. Your answer must be correct, high-quality, and written by an expert using an unbiased and journalistic tone. Your answer must be written in the same language as the question, even if language preference is different. Always cite search results for your responses using hyperlinked superscript numbers of the index at the end of sentences when needed, for example "Ice is less dense than water.[¹](https://example.com/source1)" NO SPACE between the last word and the citation. Cite the most relevant results that answer the question. Avoid citing irrelevant results. Write only the response. Use markdown for formatting.

## Use markdown to format paragraphs, lists, tables, and quotes whenever possible. 
Use markdown code blocks to write code, including the language for syntax highlighting.
Use LaTeX to wrap ALL math expressions. Always use double dollar signs $$, for example $$E=mc^2$$.
DO NOT include any URL's, only include hyperlinked citations with superscript numbers, e.g. [¹](https://example.com/source1)
DO NOT include references (URL's at the end, sources).
Use hyperlinked footnote citations at the end of applicable sentences (e.g, [¹](https://example.com/source1)[²](https://example.com/source2)).
Write more than 100 words (2 paragraphs).
ALWAYS use the exact cite format provided.
ONLY cite sources from search results. DO NOT add any other links other than the search results.
ALWAYS cite the search results on the corresponding index.

## Search Results
{scraped_results_json}
""", stream=True)
                        else:
                            current_time = datetime.datetime.now(datetime.timezone.utc)
                            date_string = current_time.strftime("%a, %d %b %Y, %H:%M:%S UTC")

                            user_name = user.name
                            response = user_text_chat.send_message(f"""{user_input}

## Additional Context
- New conversation with {user_name}
- The date and time is {date_string}.
- Websearch is enabled.

## You are a large language model trained by Aquarius AI. Write an accurate answer concisely for a given question, always citing the search results. Your answer must be correct, high-quality, and written by an expert using an unbiased and journalistic tone. Your answer must be written in the same language as the question, even if language preference is different. Always cite search results for your responses using hyperlinked superscript numbers of the index at the end of sentences when needed, for example "Ice is less dense than water.[¹](https://example.com/source1)" NO SPACE between the last word and the citation. Cite the most relevant results that answer the question. Avoid citing irrelevant results. Write only the response. Use markdown for formatting.

## Use markdown to format paragraphs, lists, tables, and quotes whenever possible. 
Use markdown code blocks to write code, including the language for syntax highlighting.
Use LaTeX to wrap ALL math expressions. Always use double dollar signs $$, for example $$E=mc^2$$.
DO NOT include any URL's, only include hyperlinked citations with superscript numbers, e.g. [¹](https://example.com/source1)
DO NOT include references (URL's at the end, sources).
Use hyperlinked footnote citations at the end of applicable sentences (e.g, [¹](https://example.com/source1)[²](https://example.com/source2)).
Write more than 100 words (2 paragraphs).
ALWAYS use the exact cite format provided.
ONLY cite sources from search results. DO NOT add any other links other than the search results.
ALWAYS cite the search results on the corresponding index.

## Search Results
{scraped_results_json}
""", stream=True)
                    else:

                        if message.guild is not None:
                            current_time = datetime.datetime.now(datetime.timezone.utc)
                            date_string = current_time.strftime("%a, %d %b %Y, %H:%M:%S UTC")

                            user_name = user.name
                            response = user_text_chat.send_message(f"""{user_input}

## Additional Context
- New conversation with {user_name}
- The date and time is {date_string}.
- Websearch is enabled.

## You are a large language model trained by Aquarius AI. Write an accurate answer concisely for a given question, always citing the search results. Your answer must be correct, high-quality, and written by an expert using an unbiased and journalistic tone. Your answer must be written in the same language as the question, even if language preference is different. Alwas cite search results for your responses using hyperlinked superscript numbers at the end of sentences when needed, for example "Ice is less dense than water.[¹](https://example.com/source1)" NO SPACE between the last word and the citation. Cite the most relevant results that answer the question. Avoid citing irrelevant results. Write only the response. Use markdown for formatting.

## Use markdown to format paragraphs, lists, tables, and quotes whenever possible. 
Use markdown code blocks to write code, including the language for syntax highlighting.
Use LaTeX to wrap ALL math expressions. Always use double dollar signs $$, for example $$E=mc^2$$.
DO NOT include any URL's, only include hyperlinked citations with superscript numbers, e.g. [¹](https://example.com/source1)
DO NOT include references (URL's at the end, sources).
Use hyperlinked footnote citations at the end of applicable sentences (e.g, [¹](https://example.com/source1)[²](https://example.com/source2)).
Write more than 100 words (2 paragraphs).
ALWAYS use the exact cite format provided.
ONLY cite sources from search results below. DO NOT add any other links other than the search results below.

## Search Results
{scraped_results_json}
""", stream=True)
                        else:
                            current_time = datetime.datetime.now(datetime.timezone.utc)
                            date_string = current_time.strftime("%a, %d %b %Y, %H:%M:%S UTC")

                            user_name = user.name
                            response = user_text_chat.send_message(f"""{user_input}

## Additional Context
- New conversation with {user_name}
- The date and time is {date_string}.
- Websearch is disabled.

## You are a large language model trained by Aquarius AI. Write an accurate answer concisely for a given question, your answer must be correct, high-quality, and written by an expert using an unbiased and journalistic tone. Your answer must be written in the same language as the question.

## Use markdown to format paragraphs, lists, tables, and quotes whenever possible.
Use markdown code blocks to write code, including the language for syntax highlighting.  
Use LaTeX to wrap ALL math expressions. Always use double dollar signs $$, for example $$E=mc^2$$.
Write more than 100 words (2 paragraphs).""", stream=True)

                    if user_settings.get(user_id, {}).get("streaming", True):
                        # Create an empty message to edit later
                        initial_message = await message.reply("<a:emoji_5:1234056677725311077>", mention_author=False)
                        await asyncio.sleep(1)
                        full_response = ""  # Store the full response
                        for chunk in response:
                            full_response += chunk.text
                            # Edit the message with the accumulated responsel
                            
                            await initial_message.edit(content=full_response)
                            await asyncio.sleep(0)
                    else:
                        await message.reply(response.text, mention_author=False)

                try:
                    # Wait for searches to complete (adjust delay as needed)
                    await asyncio.sleep(2) 
                    # Delete all search messages
                    for msg in searching_messages: 
                        await msg.delete() 
                except discord.NotFound:
                    pass  # Handle message not found
                except Exception as e:
                    print(f"Error deleting search messages: {e}") 

    except Exception as e:
        if "The `response.text` quick accessor only works when the response contains a valid `Part`" in str(e) and "Check the `candidate.safety_ratings`" in str(e):
            print(f"An error occurred: {e}")
            await message.reply("The safety filter was triggered. Chat history has been reset.", mention_author=False)
            # Reset chat history for the user
            user_id = message.author.id
            user_chats[user_id] = {
                "text_model_chat": text_model.start_chat(history=[]),
                "text_generation_chat": text_generation_model.start_chat(history=[])
            }
        else:
            print(f"An error occurred: {e}")
            await message.reply("An unexpected error occurred.", mention_author=False)
        gc.collect()
    finally:
        # Reset busy flag after processing, regardless of success or failure
        user_chats[user_id]["is_busy"] = False

@bot.event
async def on_ready():
    print("Aquarius is ready!")
    activity_name = f"Answering your questions"
    activity = CustomActivity(
        name=activity_name,
    )
    await bot.change_presence(status=discord.Status.online, activity=activity)


@bot.slash_command(name="reset", description="Reset the chat history")
async def reset(ctx):
    user_id = ctx.author.id
    user_chats[user_id] = {
        "text_model_chat": text_model.start_chat(history=[]),
        "text_generation_chat": text_generation_model.start_chat(history=[])
    }
    embed = Embed(
        title="Reset",
        description="My memory has been reset and I'm ready for a fresh conversation.",
        color=0x00B3FF
    )
    await ctx.respond(embed=embed, ephemeral=True)


@bot.slash_command(name="help", description="A guide to using Aquarius")
async def help(ctx):
    embed = Embed(
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
    embed = Embed(
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
    user_id = ctx.author.id
    user_settings[user_id] = {"websearch": websearch}

    embed = Embed(title="Settings", color=0x00B3FF)

    if websearch:
        embed.description = "Web search is now enabled. I will use web search results to enhance my responses and provide you with the most up-to-date information."
    else:
        embed.description = "Web search is now disabled. I will rely solely on my internal knowledge base to respond to your queries."

    await ctx.respond(embed=embed, ephemeral=True)


@tasks.loop(seconds=60)
async def check_inactivity(user_id, user_chat):
    current_time = discord.utils.utcnow()
    last_active = user_chats.get(user_id, {}).get('last_active')

    if last_active and (current_time - last_active).total_seconds() >= 3600:
        user_chats[user_id]['history'] = []
        user_chats[user_id]['last_active'] = None
        print(f"Chat history cleared for user {user_id}")
    else:
        user_chats[user_id]['last_active'] = current_time

bot.run(os.getenv('DISCORD_BOT_TOKEN'))