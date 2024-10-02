# A discord bot that uses KoboldCpp's api so you can talk to it.
# Created by Honkyrot on 9/23/2024
# https://github.com/honkyrot
# Python 3.12.4
# v 0.2

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
LOCALHOST_ENDPOINT = os.getenv('LOCALHOST_ENDPOINT')

# bot should only be in one guild
ALLOW_ALL_GUILDS = True # default false, set to true if you want to allow all guilds, not recommended since memory is persistent
is_in_right_guild = False

# ai stuff
bot_name = "Cirno" # the name of the bot that will respond to
# make sure to change the instruct prompt to fit in character
always_respond_to = [] # list of names to always respond to whenever they send a message

busy = False # prevent multiple requests

allow_chat_history = True  # turn on or off chat history
chat_history = []  # store chat history
previous_prompt = ""

# stop words for koboldcpp prompt
snip_words = ["User:", "Bot:", "You:", "Me:", "{}:".format(bot_name)]
# serialize snip_words into json
snip_words = json.dumps(snip_words)

# AI samples and parameters
max_context_length = 4096 # the maximum number of tokens to hold in memory
max_length = 256 # the maximum number of tokens to generate
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
# dynamic temperature
dynamic_temperature = 'true'
dynatemp_low = 0.1
dynatemp_high = 1.5
dynatemp_range = 0.7
dynatemp_exponent = 1

# init
intents = discord.Intents.all()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
guild = None

async def sanitize_text(text):
    """removes unwanted characters from the text"""
    text = text.replace('"', '\\"')
    text = text.replace('\n', '\\n')
    text = text.replace('\\\\', '\\')
    return text

async def check_api_status():
    """checks if the koboldcpp api is online, returns True if it is
    and False if it is not"""
    test_url = f'{LOCALHOST_ENDPOINT}/api/v1/model'

    # make a GET request to the server
    response = requests.get(test_url)

    # check if the server is up
    if response.status_code == 200:
        return True
    
async def send_prompt(user, prompt):
    """Sends a pre-made prompt to the koboldcpp api."""
    post_url = f'{LOCALHOST_ENDPOINT}/api/v1/generate'

    # build the prompt. VERY IMPORTANT TO USE THE RIGHT INSTRUCT PROMPTS TO THE MODEL, and help me so please.
    # just copy it from SillyTavern...
    # MODEL NAME USED IN DEVELOPMENT: https://huggingface.co/Sao10K/L3-8B-Stheno-v3.2 Q8.0 quant
    instruct_prompt = "<|begin_of_text|><|start_header_id|>system<|end_header_id|>You are " + bot_name + ", a character from the Touhou Project. You are a chatbot designed to interact with Discord users. Respond in English. Respond with only one sentence, keep it short. Respond in plaintext. Keep your response in character. Write a response that appropriately completes the request."

    for interaction in chat_history:
        print(interaction)
        instruct_prompt += "<|eot_id|><|start_header_id|>user<|end_header_id|>" + interaction["user_name"] + ": " + interaction["user_prompt"] + "<|eot_id|><|start_header_id|>assistant<|end_header_id|>" + bot_name + ": " + interaction["bot_response"]
    
    append_prompt = "<|eot_id|><|start_header_id|>user<|end_header_id|>" + str(user) + ": " + str(prompt) + "<|eot_id|><|start_header_id|>assistant<|end_header_id|>" + bot_name + ": "

    prompt = f'"max_context_length": {max_context_length},"max_length": {max_length},"prompt": f"{instruct_prompt} {append_prompt}","quiet": {quiet},"rep_pen": {repetition_penalty},"rep_pen_range": {rep_pen_range},"rep_pen_slope": {rep_pen_slope},"temperature": {temperature},"tfs": {tfs},"top_a": {top_a},"top_k": {top_k},"top_p": {top_p},"typical": {typical},"dynamic_temperature":{dynamic_temperature},"dynatemp_low": {dynatemp_low}, "dynatemp_high": {dynatemp_high}, "dynatemp_range": {dynatemp_range}, "dynatemp_exponent": {dynatemp_exponent}, "stopping_strings": {snip_words}, "stop": {snip_words}'
    prompt = "{" + prompt + "}"
    # remove that "f" from the prompt
    prompt = prompt.replace('"prompt": f"', '"prompt": "')
    print(prompt)

    # store old prompt
    global previous_prompt
    previous_prompt = prompt
    
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

    # check api status
    if not await check_api_status():
        raise RuntimeError('koboldcpp api is not online!')
    
    print(f'{client.user} has connected to Discord!')
    
@client.event
async def on_message(message: discord.Message) -> None:
    """Responds to messages with koboldcpp."""
    do_not_save_override = False

    # Ignore messages from ourselves
    if message.author == client.user:
        return

    # Check if the bot is in the right guild
    if not ALLOW_ALL_GUILDS and message.guild.name != DISCORD_GUILD:
        return

    # Check if the bot was mentioned or if the bot name is in the message
    if client.user.mentioned_in(message) or bot_name.lower() in message.content.lower():
        # Remove the client ID when mentioned by an @
        message.content = message.content.replace(f'<@{client.user.id}>', '')
    else:
        # Check if the user matches the always_respond_to list
        if message.author.name.lower() in (name.lower() for name in always_respond_to):
            pass
        else:
            return

    # If the message is empty, don't respond
    if message.content.strip() == '':
        return
    
    # convert any @ mentions to usernames

    guild_members = message.guild.members
    for list_member in guild_members:
        message.content = message.content.replace(f'<@{list_member.id}>', list_member.name)
    
    # Check if the bot is busy
    global busy
    if busy:
        return
    busy = True
    channel = message.channel
    async with channel.typing(): # typing indicator
        # Change some characters to work with the prompt
        prompt = await sanitize_text(message.content)
        # print(f'Prompt: {prompt}')

        # Send to AI for response
        response, _ = await send_prompt(message.author, prompt)

        # Decode response
        try:
            response = json.loads(response)['results'][0]['text']
        except (KeyError, IndexError):
            await message.channel.send(f'Error: {response}')
            do_not_save_override = True
            # raise RuntimeError(f'Error: {response}')

        # Send response
        await message.channel.send(response)

        busy = False

        # Add to history
        if allow_chat_history and not do_not_save_override:
            chat_history.append(
                {'user_name': message.author.name, 'user_prompt': prompt, 'bot_response': await sanitize_text(response)}
            )
# commands below

@tree.command(name="clear_history", description="Clears the chat history of the bot.")
async def clear_chat_history(interaction: discord.Interaction):
    """Clears the chat history of the bot."""
    global chat_history
    num_interactions = len(chat_history)
    chat_history = []
    await interaction.response.send_message(
        f"Chat history cleared.\n{num_interactions} interactions removed."
    )

@tree.command(name="show_history", description="Shows 6 most recent interactions.")
async def show_chat_history(interaction: discord.Interaction):
    """Shows 6 most recent interactions."""
    global chat_history
    global previous_prompt

    temp_chat_history = []
    for i in range(6):
        temp_chat_history.append(chat_history[:].pop())

    await interaction.response.send_message(f"Showing chat history stored:\n{temp_chat_history}")

@tree.command(name="koboldcpp_api_model_name", description="Returns the current model name used by koboldcpp.")
async def get_koboldcpp_api_model_name(interaction: discord.Interaction):
    """Returns the current model name used by koboldcpp."""
    url = f'{LOCALHOST_ENDPOINT}/api/v1/model'

    # make a GET request to the server
    response = requests.get(url)

    # check if the server is up
    if response.status_code == 200:
        await interaction.response.send_message(f"The model name in use is:\n{response.text}")
    else:
        await interaction.response.send_message('Error: ' + response.text)

@tree.command(name="pop_response", description="Pops/removes the last response from the chat history.")
async def pop_response(interaction: discord.Interaction):
    """Pops/removes the last response from the chat history."""
    global chat_history
    if len(chat_history) > 0:
        pop = chat_history.pop()
        await interaction.response.send_message(f"Chat history popped, removed: {pop}")
    else:
        await interaction.response.send_message("Chat history is empty.")

try:
    client.run(DISCORD_TOKEN)
except discord.errors.LoginFailure:
    print("bot failed to login.")


# terminate with ctrl + c