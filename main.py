# A discord bot that uses KoboldCpp's api so you can talk to it.
# Created by Honkyrot on 9/23/2024
# https://github.com/honkyrot
# Python 3.12.4

# token in .env

# imports
import os
import discord
from discord import app_commands
import requests
import json
from dotenv import load_dotenv

# env
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
DISCORD_GUILD = os.getenv('DISCORD_GUILD')

ALLOW_ALL_GUILDS = True # default false, set to true if you want to allow all guilds
# stats

is_in_right_guild = False

# ai stuff
bot_name = "Cirno" # the name of the bot that will respond to
chat_history = []  # store chat history

snip_words = ["<|im_end|>", "<|"]
# serialize snip_words into json
snip_words = json.dumps(snip_words)

# AI samples and parameters
max_context_length = 2048 # the maximum number of tokens to hold in memory
max_length = 512
quiet = 'false'
repetition_penalty = 1.1
rep_pen_range = 256
rep_pen_slope = 1
temperature = 0.5
tfs = 1
top_a = 0
top_k = 100
top_p = 0.9
typical = 1

dynamic_temperature = 'true'
dynatemp_low = 0.1
dynatemp_high = 1.5
dynatemp_range = 0.7
dynatemp_exponent = 1

# init
intents = discord.Intents.all()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

async def check_koboldcpp_status():
    """checks if the koboldcpp api is online, returns True if it is
    and False if it is not"""
    localhost = 'http://localhost:5001'
    test_url = 'http://localhost:5001/api/v1/model'

    # make a GET request to the server
    response = requests.get(test_url)

    # check if the server is up
    if response.status_code == 200:
        return True
    
async def send_prompt(user, prompt):
    """Sends a pre-made prompt to the koboldcpp api."""
    post_url = 'http://localhost:5001/api/v1/generate'

    # build the prompt. VERY IMPORTANT TO USE THE RIGHT INSTRUCT PROMPTS TO THE MODEL, and help me so please.
    # just copy it from SillyTavern...
    # MODEL NAME USED IN DEVELOPMENT: https://huggingface.co/Sao10K/L3-8B-Stheno-v3.2 Q8.0 quant
    instruct_prompt = "<|begin_of_text|><|start_header_id|>system<|end_header_id|>You are " + bot_name + ", a chatbot designed to interact with users. Respond in English, respond with only one sentence. Respond in plaintext. Keep your response in character, write a response that appropriately completes the request."

    for interaction in chat_history:
        print(interaction)
        instruct_prompt += "<|eot_id|><|start_header_id|>user<|end_header_id|>" + interaction["user_name"] + ": " + interaction["user_prompt"] + "<|eot_id|><|start_header_id|>assistant<|end_header_id|>" + bot_name + ": " + interaction["bot_response"]
    
    append_prompt = "<|eot_id|><|start_header_id|>user<|end_header_id|>" + str(user) + ": " + str(prompt) + "<|eot_id|><|start_header_id|>assistant<|end_header_id|>" + bot_name + ": "

    prompt = f'"max_context_length": {max_context_length},"max_length": {max_length},"prompt": f"{instruct_prompt} {append_prompt}","quiet": {quiet},"rep_pen": {repetition_penalty},"rep_pen_range": {rep_pen_range},"rep_pen_slope": {rep_pen_slope},"temperature": {temperature},"tfs": {tfs},"top_a": {top_a},"top_k": {top_k},"top_p": {top_p},"typical": {typical},"dynamic_temperature":{dynamic_temperature},"dynatemp_low": {dynatemp_low}, "dynatemp_high": {dynatemp_high}, "dynatemp_range": {dynatemp_range}, "dynatemp_exponent": {dynatemp_exponent}, "stopping_strings": {snip_words}, "stop": {snip_words}'
    prompt = "{" + prompt + "}"
    # remove that "f" from the prompt
    prompt = prompt.replace('"prompt": f"', '"prompt": "')
    print(prompt)
    
    # pre_prompt="""{"max_context_length": 8196,"max_length": 1024,"prompt": "%s %s","quiet": false,"rep_pen": 1.1,"rep_pen_range": 256,"rep_pen_slope": 1,"temperature": 0.5,"tfs": 1,"top_a": 0,"top_k": 100,"top_p": 0.9,"typical": 1}"""

    # make API call
    response = requests.post(post_url, data=prompt)

    # wait for response text,
    return response.text, prompt

@client.event
async def on_ready() -> None:
    """Called when the bot is ready."""

    await tree.sync()

    guild = discord.utils.get(client.guilds, name=DISCORD_GUILD)

    # check if the bot is in the guild
    if guild is None:
        raise RuntimeError(f'Bot is not in the guild: {DISCORD_GUILD}')

    # check the koboldcpp api
    if not await check_koboldcpp_status():
        raise RuntimeError('Koboldcpp api is not online!')
    
    print(f'{client.user} has connected to Discord!')


@client.event
async def on_message(message):
    """on message, respond with a hello world""" 

    # don't respond to ourselves
    if message.author == client.user:
        return
    
    # vars
    user = message.author
    prompt = message.content
    guild_check = message.guild.name

    # check if the bot is in the right guild
    if not ALLOW_ALL_GUILDS and guild_check != DISCORD_GUILD:
        print("Not in right guild, skipping message, got: " + prompt)
        return

    # make sure the bot was mentioned to continue
    if not bot_name.lower() in prompt.lower():
        print(f"{bot_name} was not mentioned, skipping message, got: {prompt}")
        return
    
    # remove the backslash
    prompt = prompt.replace('\\', '')
    
    print('Message from {0.author}: {0.content}'.format(message))

    # send to AI for response
    response, stored_response = await send_prompt(user, prompt)

    decoded_response = json.loads(response)
    try:
        decoded_response = decoded_response['results'][0]['text']
    except:
        await message.channel.send('Error: ' + response)
        raise RuntimeError('Error: ' + response)
    # send response
    
    # dummy response
    #await message.channel.send('Hello!')

    # actual response, need refining process
    await message.channel.send(decoded_response)

    # if everything works, add to history
    chat_history.append({"user_name": user.name, "user_prompt": prompt, "bot_response": decoded_response})

@tree.command(
    name="clear_history",
    description="Clears the chat history of the bot.",
)

async def clear_history(interaction: discord.Interaction):
    """Clears the chat history of the bot."""
    global chat_history
    chat_history = []
    await interaction.response.send_message("Chat history cleared.")


client.run(DISCORD_TOKEN)

# terminate with ctrl + c