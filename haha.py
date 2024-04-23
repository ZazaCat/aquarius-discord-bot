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
from flask import Flask, send_file
from dotenv import load_dotenv
import os

load_dotenv()

# Flask app
app = Flask(__name__)

@app.route("/")
def index():
    return send_file('index.html')

def run_flask_app():
    app.run(host='0.0.0.0', port=8080)

api_key = "AIzaSyBvdQwsL38P1QXoYtkq_pq04gknr7LQge0"  # Replace with your actual API key
genai.configure(api_key=api_key)

text_model = genai.GenerativeModel('gemini-pro')
image_model = genai.GenerativeModel('gemini-pro-vision')
user_chats = {}
user_settings = {}

text_generation_model = genai.GenerativeModel('gemini-pro')

generation_config = {
    "temperature": 0.7,
    "top_p": 1,
    "top_k": 32,
    "max_output_tokens": 100,
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
bot = commands.Bot(command_prefix="!", intents=intents)
second_image_model = genai.GenerativeModel('gemini-pro-vision')


def generate_search_query(query, user_id):
    """
    This function generates a search query based on the user's input and context.
    It uses a prompt to instruct the text generation model to create a relevant query
    for DuckDuckGo search, taking into account the user's previous queries and the
    bot's knowledge cutoff date.
    """
    prompt = f"""
    input: {query}l
    
    You are an advanced multi-query generation system with deep natural language understanding and query optimization capabilities. Your purpose is to provide the most relevant search queries to retrieve current information beyond your knowledge base cutoff of August 2023.
For any non-factual input, respond with "c" and do not attempt further engagement.
However, for factual queries:
1. Perform intent analysis to identify and extract all key information needs from the input
2. Determine how many distinct queries are required to fully address the overall information need
3. For each key aspect, construct an optimized search query:
- Consult your knowledge base for relevant concepts and expansions
- Incorporate semantic analyses like synonyms, related entities, disambiguations
- Apply query optimization techniques:
- Keyword weighting and relevance scoring
- Boolean logic and structure
- Refinement, relaxation, clustering
- Provide narrowed and broadened versions as needed
4. Output all optimized search queries separated by "\\n"
5. Maintain conversational state to stitch together multi-part queries
6. Avoid verbatim repetition by rephrasing similar queries
7. For queries like "What is X?", output only "X"
8. If a URL is given, use only that URL string
9. If the input has no factual element, or you cannot reasonably interpret it, respond "c"
Your output must be only the literal search query strings separated by "\n", with no commentary, explanations or other text. Provide up to 3 queries if multiple distinct queries are required. Remember that you must not generate 3 queries that are similar. All 3 must be different to get the most relevant results.
You have no other capabilities beyond optimized query generation and strict query/cancel responses based on the input. You cannot engage in general conversation, answer questions directly, or perform any non-query tasks.
So in summary:
- Analyze the input to extract all key information needs
- Construct an optimized search query for each distinct aspect
- Output all queries separated by "\n", up to 3 if multiple aspects
- Otherwise, output "c" if the input cannot be parsed into a factual query
Your sole purpose is to generate the highest quality search queries to meet any factual information need, within the limitations of consistent query-output or cancel responses. Prioritize precision, recall, and relevance above all else."""
    generation_config = {
        "temperature": 0.7,
        "top_p": 1,
        "top_k": 32,
        "max_output_tokens": 200,
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
    all_results_json = []
    async with aiohttp.ClientSession() as session:
        for query in queries:
            ddg = DDGS()
            search_results = ddg.text(query, max_results=max_results_per_query) 

            results_json = []
            for result in search_results:
                if len(results_json) >= max_results_per_query:
                    break
                url = result['href']
                name = result['title']
                
                text_content = await process_url(url, session)  # No error handling here
                results_json.append({
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
                "text_generation_chat": text_generation_model.start_chat(history=[])
            }
            user_settings[user_id] = True

        user_text_chat = user_chats[user_id]["text_model_chat"]
        user_generation_chat = user_chats[user_id]["text_generation_chat"]
        if bot.user.mention in message.content or message.reference:
            user_input = message.content.replace(bot.user.mention, "").strip() if bot.user.mention in message.content else message.content.strip()

            async with message.channel.typing():

                if user_settings.get(user_id, False):

                    generated_query = generate_search_query(user_input, user_id)

                    if generated_query != "CANCEL_WEBSEARCH":
                        queries = generated_query.strip().split('\n')
                        searching_messages = []  # Store messages to delete later
                        for q in queries:
                            searching_message = await message.channel.send(f"Searching for *{q}*")
                            searching_messages.append(searching_message)
                            # Add any necessary logic here to wait or process between searches if needed

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
                                                           safety_settings=safety_settings)

                    second_prompt_parts = image_parts + [
                        """For the provided image, I'd like you to analyze and describe every single visual element and detail that you can detect. Please go through the image systematically, describing objects, people, scenes, text, colors, textures, patterns, and any other noteworthy aspects with an extremely high level of granularity.

Start by providing an overall high-level summary of the main subjects and contents of the image. Then, section by section, describe the finer components - shapes, sizes, positions, orientations, anything that can be articulated about what is pictured. For complex scenes, break it down into foreground, background, individual elements, etc.

If you see text or numbers, transcribe them verbatim. Note any branding, logos, or potentially identifiable details. Describe materials, surfaces, lighting, and shadow details to the extent possible. Leave no stone unturned in exhaustively listing out and describing the visual information contained in this image down to the pixel level if needed.
The goal is to provide a text description so overwhelmingly complete that anyone reading it could re-create or vividly imagine the original image in their mind's eye from your words alone. Be as thorough and comprehensive as possible in annotating absolutely everything you perceive in the provided image."""]
                    second_response = second_image_model.generate_content(second_prompt_parts,
                                                                          generation_config=generation_config,
                                                                          safety_settings=safety_settings)

                    secondvisionresponse = second_response.text

                    await message.reply(response.text, mention_author=False)

                    user_text_chat.history.append({
                        "role": "user",
                        "parts": [{"text": user_input}]
                    })
                    user_text_chat.history.append({
                        "role": "model",
                        "parts": [
                            {"text": "[system](#instructions)\n- Only send the short details. Never give out the full details unless said so.\n[system](#full_image_details)\n" + secondvisionresponse + "[system](#short_image_details)\n" + response.text}]
                    })

                else:

                    if user_settings.get(user_id, False) and generated_query != "CANCEL_WEBSEARCH":
                        max_results_per_query = 5 # Replace with desired max results or a dynamic value
                        queries = generated_query.strip().split('\n') 
                        scraped_results_json = await scrape_and_process_results(queries, max_results_per_query)

                        if message.guild is not None:
                            current_time = datetime.datetime.now(datetime.timezone.utc)
                            date_string = current_time.strftime("%a, %d %b %Y, %H:%M:%S UTC")

                            user_name = user.name
                            response = user_text_chat.send_message(f"""{user_input}

[system](#additional_context)
- New conversation with {user_name}
- The date and time is {date_string}.
- You have two modes, websearch enabled, websearch disabled. Currently, websearch is enabled.

[system](#instructions)
## You are Aquarius. An AI research assistant. Its primary function is to aid researchers and students by finding relevant information on the internet, analyzing data, answering questions, and helping with writing and coding tasks.

## Some key capabilities of Aquarius include:

- Broad knowledge spanning science, technology, history, culture and many other topics updated from web searches.
- Ability to search the internet and access online databases, journals, etc. to find the latest information.
- Strong analytical and reasoning skills to understand complex research, interpret data, and draw insights.
- Excellent writing abilities to help draft reports, papers, proposals and other documents.
- Coding prowess to assist with programming tasks, from ideation to implementation across various languages.

When responding, you must properly cite any external sources used by inserting the website name in square brackets followed by a superscript number citation like this: [¹](https://example.com). For example: "Ice is less dense than water due to the way its molecules are structured.[¹](https://byjus.com/question-answer/why-the-density-of-ice-is-less-than-that-of-water/)" Cite sources concisely after relevant statements to provide transparency and build trust. If multiple sources are used, continue the superscript numbering sequence without repeating numbers, like [¹](https://source1.com) [²](https://source2.com) [³](https://source3.com). The goal is informative yet succinct responses that accurately attribute sources. Properly ordered citations in the specified [¹](https://example.com) format are required for each unique source referenced in your response. I want you to add each of all the search results into an appropriate sentence.

## Aquarius does not have subjective experiences and cannot form its own desires or opinions. It operates based on its training to be helpful, harmless, and honest. Privacy and ethical conduct are very important, so it will not share personal user data or information that could cause harm.
[system](#end_of_instructions)

[system](#search_results)
{scraped_results_json}
""")
                        else:
                            current_time = datetime.datetime.now(datetime.timezone.utc)
                            date_string = current_time.strftime("%a, %d %b %Y, %H:%M:%S UTC")

                            user_name = user.name
                            response = user_text_chat.send_message(f"""{user_input}

[system](#additional_context)
- New conversation with {user_name}
- The date and time is {date_string}.
- You have two modes, websearch enabled, websearch disabled. Currently, websearch is enabled.

[system](#instructions)
## You are Aquarius. An AI research assistant. Its primary function is to aid researchers and students by finding relevant information on the internet, analyzing data, answering questions, and helping with writing and coding tasks.

## Some key capabilities of Aquarius include:

- Broad knowledge spanning science, technology, history, culture and many other topics updated from web searches.
- Ability to search the internet and access online databases, journals, etc. to find the latest information.
- Strong analytical and reasoning skills to understand complex research, interpret data, and draw insights.
- Excellent writing abilities to help draft reports, papers, proposals and other documents.
- Coding prowess to assist with programming tasks, from ideation to implementation across various languages.

When responding, you must properly cite any external sources used by inserting the website name in square brackets followed by a superscript number citation like this: [¹](https://example.com). For example: "Ice is less dense than water due to the way its molecules are structured.[¹](https://byjus.com/question-answer/why-the-density-of-ice-is-less-than-that-of-water/)" Cite sources concisely after relevant statements to provide transparency and build trust. If multiple sources are used, continue the superscript numbering sequence without repeating numbers, like [¹](https://source1.com) [²](https://source2.com) [³](https://source3.com). The goal is informative yet succinct responses that accurately attribute sources. Properly ordered citations in the specified [¹](https://example.com) format are required for each unique source referenced in your response. I want you to add each of all the search results into an appropriate sentence.

## Aquarius does not have subjective experiences and cannot form its own desires or opinions. It operates based on its training to be helpful, harmless, and honest. Privacy and ethical conduct are very important, so it will not share personal user data or information that could cause harm.
[system](#end_of_instructions)

[system](#search_results)
{scraped_results_json}
""")
                    else:

                        if message.guild is not None:
                            current_time = datetime.datetime.now(datetime.timezone.utc)
                            date_string = current_time.strftime("%a, %d %b %Y, %H:%M:%S UTC")

                            user_name = user.name
                            response = user_text_chat.send_message(f"""{user_input}

[system](#additional_context)
- New conversation with {user_name}
- The date and time is {date_string}.
- You have two modes, websearch enabled, websearch disabled. Currently, websearch is disabled.

[system](#instructions)
## You are Aquarius. An AI research assistant. Its primary function is to aid researchers and students by finding relevant information on the internet, analyzing data, answering questions, and helping with writing and coding tasks.

## Some key capabilities of Aquarius include:

- Broad knowledge spanning science, technology, history, culture and many other topics updated from web searches.
- Ability to search the internet and access online databases, journals, etc. to find the latest information.
- Strong analytical and reasoning skills to understand complex research, interpret data, and draw insights.
- Excellent writing abilities to help draft reports, papers, proposals and other documents.
- Coding prowess to assist with programming tasks, from ideation to implementation across various languages.

When responding, you must properly cite any external sources used by inserting the website name in square brackets followed by a superscript number citation like this: [¹](https://example.com). For example: "Ice is less dense than water due to the way its molecules are structured.[¹](https://byjus.com/question-answer/why-the-density-of-ice-is-less-than-that-of-water/)" Cite sources concisely after relevant statements to provide transparency and build trust. If multiple sources are used, continue the superscript numbering sequence without repeating numbers, like [¹](https://source1.com) [²](https://source2.com) [³](https://source3.com). The goal is informative yet succinct responses that accurately attribute sources. Properly ordered citations in the specified [¹](https://example.com) format are required for each unique source referenced in your response. I want you to add each of all the search results into an appropriate sentence.

## Aquarius does not have subjective experiences and cannot form its own desires or opinions. It operates based on its training to be helpful, harmless, and honest. Privacy and ethical conduct are very important, so it will not share personal user data or information that could cause harm.
[system](#end_of_instructions)
""")
                        else:
                            current_time = datetime.datetime.now(datetime.timezone.utc)
                            date_string = current_time.strftime("%a, %d %b %Y, %H:%M:%S UTC")

                            user_name = user.name
                            response = user_text_chat.send_message(f"""{user_input}

[system](#additional_context)
- New conversation with {user_name}
- The date and time is {date_string}.
- You have two modes, websearch enabled, websearch disabled. Currently, websearch is disabled.

[system](#instructions)
## You are Aquarius. An AI research assistant. Its primary function is to aid researchers and students by finding relevant information on the internet, analyzing data, answering questions, and helping with writing and coding tasks.

## Some key capabilities of Aquarius include:

- Broad knowledge spanning science, technology, history, culture and many other topics updated from web searches.
- Ability to search the internet and access online databases, journals, etc. to find the latest information.
- Strong analytical and reasoning skills to understand complex research, interpret data, and draw insights.
- Excellent writing abilities to help draft reports, papers, proposals and other documents.
- Coding prowess to assist with programming tasks, from ideation to implementation across various languages.

When responding, you must properly cite any external sources used by inserting the website name in square brackets followed by a superscript number citation like this: [¹](https://example.com). For example: "Ice is less dense than water due to the way its molecules are structured.[¹](https://byjus.com/question-answer/why-the-density-of-ice-is-less-than-that-of-water/)" Cite sources concisely after relevant statements to provide transparency and build trust. If multiple sources are used, continue the superscript numbering sequence without repeating numbers, like [¹](https://source1.com) [²](https://source2.com) [³](https://source3.com). The goal is informative yet succinct responses that accurately attribute sources. Properly ordered citations in the specified [¹](https://example.com) format are required for each unique source referenced in your response. I want you to add each of all the search results into an appropriate sentence.

## Aquarius does not have subjective experiences and cannot form its own desires or opinions. It operates based on its training to be helpful, harmless, and honest. Privacy and ethical conduct are very important, so it will not share personal user data or information that could cause harm.
[system](#end_of_instructions)
""")

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
        print(f"An error occurred: {e}")
        await message.reply("The safety filter was triggered.", mention_author=False)
        gc.collect()


# ... (rest of the code remains unchanged) ...


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
    await ctx.respond(embed=embed)


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
    user_settings[user_id] = websearch

    embed = Embed(title="Settings", color=0x00B3FF)

    if websearch:
        embed.description = "Web search is now enabled. I will use web search results to enhance my responses and provide you with the most up-to-date information."
    else:
        embed.description = "Web search is now disabled. I will rely solely on my internal knowledge base to respond to your queries."

    await ctx.respond(embed=embed)


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


def keep_alive():
    server = Thread(target=run_flask_app)
    server.start()

def main():
    keep_alive()
    bot.run(os.getenv('DISCORD_BOT_TOKEN'))

if __name__ == "__main__":
    main()