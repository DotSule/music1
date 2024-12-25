import discord
from discord.ext import commands
from discord import app_commands
import requests
import io
import random
import aiohttp
import asyncio
import re
import os
import sys
import traceback
import datetime
from keep_alive import keep_alive

# Intents and bot setup
intents = discord.Intents.all()
intents.members = True
bot = commands.Bot(command_prefix='?', intents=intents)

# Helper functions
async def GetMessage(ctx, contentOne="Default Message", contentTwo="\uFEFF", timeout=100):
    embed = discord.Embed(title=f"{contentOne}", description=f"{contentTwo}")
    sent = await ctx.send(embed=embed)
    try:
        msg = await bot.wait_for(
            "message",
            timeout=timeout,
            check=lambda message: message.author == ctx.author and message.channel == ctx.channel,
        )
        if msg:
            return msg.content
    except asyncio.TimeoutError:
        return False

time_regex = re.compile(r"(?:(\d{1,5})(h|s|m|d))+?")
time_dict = {"h": 3600, "s": 1, "m": 60, "d": 86400}

def convert(argument):
    args = argument.lower()
    matches = re.findall(time_regex, args)
    time = 0
    for key, value in matches:
        try:
            time += time_dict[value] * float(key)
        except KeyError:
            raise commands.BadArgument(
                f"{value} is an invalid time key! h|m|s|d are valid arguments"
            )
        except ValueError:
            raise commands.BadArgument(f"{key} is not a number!")
    return round(time)

# Event Handlers
@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Streaming(name="on twitch", url="https://www.twitch.tv/dotsule"))
    print('{0.user} is online!'.format(bot))

@bot.event
async def on_command_error(ctx, error):
    if hasattr(ctx.command, 'on_error'):
        return

    cog = ctx.cog
    if cog:
        if cog._get_overridden_method(cog.cog_command_error) is not None:
            return

    ignored = (commands.CommandNotFound, )
    error = getattr(error, 'original', error)

    if isinstance(error, ignored):
        return

    if isinstance(error, commands.DisabledCommand):
        await ctx.send(f'{ctx.command} has been disabled.')

    elif isinstance(error, commands.NoPrivateMessage):
        try:
            await ctx.author.send(f'{ctx.command} can not be used in Private Messages.')
        except discord.HTTPException:
            pass

    elif isinstance(error, commands.BadArgument):
        if ctx.command.qualified_name == 'tag list':
            await ctx.send('I could not find that member. Please try again.')

    else:
        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

# Commands

# Store giveaways information
giveaways = {}

# Helper function to convert time
def convert(time_str):
    units = {'d': 86400, 'h': 3600, 'm': 60, 's': 1}
    match = re.match(r"(\d+)([dhms])", time_str)
    if match:
        amount, unit = match.groups()
        return int(amount) * units[unit]
    return 0

@bot.tree.command(name="giveaway", description="Start a giveaway.")
@app_commands.describe(channel="The channel to host the giveaway", duration="How long the giveaway should last (e.g., 1d, 2h, 30m)", prize="What you are giving away")
async def giveaway(interaction: discord.Interaction, channel: discord.TextChannel, duration: str, prize: str):
    # Check if the user has admin permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You do not have the required permissions to start a giveaway.")
        return

    await interaction.response.send_message("Starting the giveaway...")

    # Convert duration to seconds
    time = convert(duration)
    if time == 0:
        await interaction.followup.send("Invalid duration format. Use d|h|m|s.")
        return

    # Create and send giveaway embed
    giveawayEmbed = discord.Embed(
        title="🎉 __**Giveaway**__ 🎉",
        description=prize
    )
    giveawayEmbed.set_footer(text=f"This giveaway ends in {duration}.")
    giveawayMessage = await channel.send(embed=giveawayEmbed)
    await giveawayMessage.add_reaction("🎉")

    # Store giveaway info
    giveaways[giveawayMessage.id] = {
        "channel_id": channel.id,
        "duration": time,
        "creator_id": interaction.user.id,
        "prize": prize
    }

    # Wait for the duration of the giveaway
    await asyncio.sleep(time)

    # Fetch the message and determine the winner
    message = await channel.fetch_message(giveawayMessage.id)
    users = [user async for user in message.reactions[0].users()]  # Collect users from the async generator
    users = [user for user in users if user != bot.user and user != interaction.user]

    if not users:
        await channel.send("No one participated in the giveaway.")
        return

    winner = random.choice(users)
    await channel.send(f"**Congrats {winner.mention}!**\nPlease contact {interaction.user.mention} about your prize.")

@bot.tree.command(name="reroll", description="Reroll the giveaway winner.")
@app_commands.describe(giveaway_message_id="The message ID of the giveaway")
async def reroll(interaction: discord.Interaction, giveaway_message_id: int):
    # Check if the user has admin permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You do not have the required permissions to reroll a giveaway.")
        return

    # Retrieve giveaway info
    giveaway = giveaways.get(giveaway_message_id)
    if not giveaway:
        await interaction.response.send_message("Giveaway not found or expired.")
        return

    channel = bot.get_channel(giveaway["channel_id"])
    if not channel:
        await interaction.response.send_message("Channel not found.")
        return

    try:
        message = await channel.fetch_message(giveaway_message_id)
    except discord.NotFound:
        await interaction.response.send_message("Giveaway message not found.")
        return

    # Determine new winner
    users = [user async for user in message.reactions[0].users()]  # Collect users from the async generator
    users = [user for user in users if user != bot.user and user != interaction.user]

    if not users:
        await interaction.response.send_message("No participants found for reroll.")
        return

    new_winner = random.choice(users)
    await interaction.response.send_message(f"**New winner: {new_winner.mention}!**")



@bot.tree.command(name="botinfo", description="Get information about the bot.")
async def botinfo(interaction: discord.Interaction):
    embed = discord.Embed(
        title='The bot info',
        description='Name = Just read it, that\'s not so hard \n \n Created = Thu, 25 Feb 2021 08:53 AM \n \n Creator = <@565054522569916426>',
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="minecraft", description="Get Minecraft server info.")
@app_commands.describe(server_name="The name of the Minecraft server.")
async def minecraft(interaction: discord.Interaction, server_name: str):
    r = requests.get(f'https://api.minehut.com/server/{server_name}?byName=true')
    json_data = r.json()

    description = json_data["server"]["motd"]
    online = str(json_data["server"]["online"])
    playerCount = str(json_data["server"]["playerCount"])

    embed = discord.Embed(
        title=f"{server_name} Server Info",
        description=f'Description: {description}\nOnline: {online}\nPlayers: {playerCount}',
        color=discord.Color.dark_green()
    )
    embed.set_thumbnail(url="https://i1.wp.com/www.craftycreations.net/wp-content/uploads/2019/08/Grass-Block-e1566147655539.png?fit=500%2C500&ssl=1")

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="c15923", description="Send a message in DM.")
async def c15923(interaction: discord.Interaction):
    await interaction.response.send_message('Sending nitro in DMs')
    await interaction.user.send('lol imagine trying')



@bot.tree.command(name="mute", description="Mute a member.")
@app_commands.describe(member="The member to mute.")
async def mute(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("You don't have permissions to use this command!")

    embed = discord.Embed(title=f'{member.mention} has been muted!', description='', color=discord.Color.green())
    role = discord.utils.get(interaction.guild.roles, name='Muted')
    await member.add_roles(role)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="warn", description="Warn a member.")
@app_commands.describe(member="The member to warn", message="The warning message.")
async def warn(interaction: discord.Interaction, member: discord.Member, *, message: str):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("You don't have permissions to use this command!")

    embed = discord.Embed(title=f'`{message}` warned by {interaction.user.name}', description='', color=discord.Color.green())
    await member.send(embed=embed)
    await interaction.response.send_message(f"Warning sent to {member.mention}")

@bot.tree.command(name="unmute", description="Unmute a member.")
@app_commands.describe(member="The member to unmute.")
async def unmute(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("You don't have permissions to use this command!")

    embed = discord.Embed(title=f'{member.mention} has been unmuted!', description='', color=discord.Color.green())
    role = discord.utils.get(interaction.guild.roles, name='Muted')
    await member.remove_roles(role)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="kick", description="Kick a member.")
@app_commands.describe(member="The member to kick.")
async def kick(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.kick_members:
        return await interaction.response.send_message("You don't have permissions to use this command!")

    await member.kick()
    await interaction.response.send_message(f'**{member.name}** has been kicked.')

@bot.tree.command(name="ban", description="Ban a member.")
@app_commands.describe(member="The member to ban.")
async def ban(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.ban_members:
        return await interaction.response.send_message("You don't have permissions to use this command!")

    await member.ban()
    await interaction.response.send_message(f'**{member.name}** has been banned.')

@bot.tree.command(name="unban", description="Unban a member.")
@app_commands.describe(member_id="The ID of the member to unban.")
async def unban(interaction: discord.Interaction, member_id: int):
    if not interaction.user.guild_permissions.ban_members:
        return await interaction.response.send_message("You don't have permissions to use this command!")

    user = await bot.fetch_user(member_id)
    await interaction.guild.unban(user)
    await interaction.response.send_message(f'**{user.name}** has been unbanned.')


# Fetch a random fact
@bot.tree.command(name="fact", description="Get a random fact")
async def fact_command(interaction: discord.Interaction):
    async with aiohttp.ClientSession() as session:
        async with session.get('https://uselessfacts.jsph.pl/random.json?language=en') as response:
            data = await response.json()
            fact = data['text']
    await interaction.response.send_message(f"Here's a random fact: {fact}")

# Fetch a random quote
@bot.tree.command(name="quote", description="Get a random inspirational quote")
async def quote_command(interaction: discord.Interaction):
    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.quotable.io/random') as response:
            data = await response.json()
            quote = data['content']
            author = data['author']
    await interaction.response.send_message(f"\"{quote}\" - {author}")

# Fetch weather information
@bot.tree.command(name="weather", description="Get the current weather for a location")
@app_commands.describe(location="The location to get the weather for")
async def weather_command(interaction: discord.Interaction, location: str):
    api_key = os.getenv('WEATHER_API_KEY')
    async with aiohttp.ClientSession() as session:
        async with session.get(f'http://api.openweathermap.org/data/2.5/weather?q={location}&appid={api_key}&units=metric') as response:
            data = await response.json()
            if data.get('cod') != 200:
                await interaction.response.send_message(f"Could not find weather data for {location}.")
                return
            temp = data['main']['temp']
            description = data['weather'][0]['description']
            city = data['name']
            await interaction.response.send_message(f"The current weather in {city} is {temp}°C with {description}.")

# Provide a trivia question
@bot.tree.command(name="trivia", description="Get a random trivia question")
async def trivia_command(interaction: discord.Interaction):
    async with aiohttp.ClientSession() as session:
        async with session.get('https://opentdb.com/api.php?amount=1&type=multiple') as response:
            data = await response.json()
            question = data['results'][0]['question']
            correct_answer = data['results'][0]['correct_answer']
            incorrect_answers = data['results'][0]['incorrect_answers']
            options = [correct_answer] + incorrect_answers
            random.shuffle(options)
            options_str = '\n'.join(f"{chr(97+i)}) {opt}" for i, opt in enumerate(options))
    await interaction.response.send_message(f"**Question:** {question}\n\n**Options:**\n{options_str}\n\nReply with the letter corresponding to your answer!")

# Send a random cat image
@bot.tree.command(name="cat", description="Get a random cat image")
async def cat_command(interaction: discord.Interaction):
    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.thecatapi.com/v1/images/search') as response:
            data = await response.json()
            cat_url = data[0]['url']
    await interaction.response.send_message(f"Here's a cute cat for you: {cat_url}")

# Flip a coin
@bot.tree.command(name="coinflip", description="Flip a coin and get heads or tails")
async def coinflip_command(interaction: discord.Interaction):
    result = random.choice(["Heads", "Tails"])
    await interaction.response.send_message(f"The coin landed on: {result}")

# Perform a mathematical calculation
@bot.tree.command(name="math", description="Perform a simple mathematical calculation")
@app_commands.describe(equation="The mathematical equation to evaluate")
async def math_command(interaction: discord.Interaction, equation: str):
    try:
        result = eval(equation)
        await interaction.response.send_message(f"The result of `{equation}` is `{result}`.")
    except Exception as e:
        await interaction.response.send_message(f"Error evaluating the equation: {e}")

# Roll a dice
@bot.tree.command(name="roll", description="Roll a dice and get a result")
@app_commands.describe(sides="The number of sides on the dice")
async def roll_command(interaction: discord.Interaction, sides: int = 6):
    result = random.randint(1, sides)
    await interaction.response.send_message(f"You rolled a {result} on a {sides}-sided dice.")

# Reverse a string
@bot.tree.command(name="reverse", description="Reverse a given string")
@app_commands.describe(text="The text to reverse")
async def reverse_command(interaction: discord.Interaction, text: str):
    reversed_text = text[::-1]
    await interaction.response.send_message(f"The reverse of `{text}` is `{reversed_text}`.")

# Create a poll
@bot.tree.command(name="poll", description="Create a simple poll")
@app_commands.describe(question="The question for the poll", options="Comma-separated options for the poll")
async def poll_command(interaction: discord.Interaction, question: str, options: str):
    options_list = [opt.strip() for opt in options.split(',')]
    options_str = '\n'.join(f"{chr(97+i)}) {opt}" for i, opt in enumerate(options_list))
    poll_embed = discord.Embed(title="Poll", description=f"**{question}**\n\n{options_str}", color=discord.Color.blue())
    message = await interaction.response.send_message(embed=poll_embed)
    for i in range(len(options_list)):
        await message.add_reaction(chr(127462 + i))  # Add reactions for each option (🇦, 🇧, etc.)

@bot.tree.command(name="help", description="Show help information.")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title='Available Commands',
        description='Here are the commands you can use, organized by category:',
        color=discord.Color.green()
    )

    # General Commands
    embed.add_field(
        name='**General**',
        value='/botinfo - Get information about the bot.\n'
              '/minecraft - Get Minecraft server info.\n',
        inline=False
    )

    # Moderation Commands
    embed.add_field(
        name='**Moderation**',
        value='/mute - Mute a member.\n'
              '/warn - Warn a member.\n'
              '/unmute - Unmute a member.\n'
              '/kick - Kick a member.\n'
              '/ban - Ban a member.\n'
              '/unban - Unban a member.\n',
        inline=False
    )

    # Miscellaneous Commands
    embed.add_field(
        name='**Miscellaneous**',
        value='/giveaway - Start a giveaway.\n'
              '/c15923 - gives  nitro link in dms.\n',
        inline=False
    )

    await interaction.response.send_message(embed=embed)


# Sync commands with Discord
@bot.event
async def on_ready():
    # Sync commands with Discord's API
    try:
        synced = await bot.tree.sync()
        print(f'Successfully synced {len(synced)} commands.')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

    print(f'Logged in as {bot.user.name}')

keep_alive()
bot.run(os.getenv('TOKEN'))
