import os
import random

from dotenv import load_dotenv
import discord
from discord import app_commands
from discord.ext import commands
import asyncio

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

answers = ["yessir","hell nah","sure g","not sure","yeah","yup"]

bot = commands.Bot(command_prefix="/", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'We have logged in as {bot.user}')
    await bot.change_presence(activity=discord.Game('Genshin Impact'))
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Error syncing commands: {e}')

@bot.tree.command(name="strike", description="Strike another user")
async def strike(interaction: discord.Interaction, player: discord.Member):
    user_name = interaction.user.display_name
    player_name = player.display_name
    embed = discord.Embed(title=f"{user_name} launched a dildo to {player_name}")
    image_url = "https://media1.tenor.com/m/ppMPMVR2SpMAAAAd/dildo-gun.gif"
    embed.set_image(url=image_url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="oil-up", description="oil up another hommie")
async def strike(interaction: discord.Interaction, player: discord.Member):
    user_name = interaction.user.display_name
    player_name = player.display_name
    embed = discord.Embed(title=f"{user_name} oiled {player_name}")
    image_url = "https://media1.tenor.com/m/CXOItGL-rjwAAAAC/dad-noel-noeldeyzel.gif"
    embed.set_image(url=image_url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="punish", description="drill someones arse/")
async def strike(interaction: discord.Interaction, player: discord.Member):
    user_name = interaction.user.display_name
    player_name = player.display_name
    embed = discord.Embed(title=f"{user_name} drilled {player_name}")
    image_url = "https://i.imgur.com/VUWWN10.gif"
    embed.set_image(url=image_url)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="crown", description="get crowned")
async def strike(interaction: discord.Interaction, player: discord.Member):
    user_name = interaction.user.display_name
    player_name = player.display_name
    embed = discord.Embed(title=f"{user_name} crowned {player_name}")
    image_url = "https://i.giphy.com/fYpUBttlicUM5hpSM2.gif"
    embed.set_image(url=image_url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="lure", description="lure a hommie into a trap")
async def strike(interaction: discord.Interaction, player: discord.Member):
    user_name = interaction.user.display_name
    player_name = player.display_name
    embed = discord.Embed(title=f"{user_name} lured {player_name}")
    image_url = "https://media1.tenor.com/m/Meo_9L0TqfAAAAAC/gypsy-belly-dancing.gif"
    embed.set_image(url=image_url)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="assert-dominance", description="who's the boss now ?")
async def strike(interaction: discord.Interaction, player: discord.Member):
    user_name = interaction.user.display_name
    player_name = player.display_name
    embed = discord.Embed(title=f"{user_name} slaped the hell outta {player_name}")
    image_url = "https://media1.tenor.com/m/OOKQrqKgFCsAAAAd/angry-kid.gif"
    embed.set_image(url=image_url)
    await interaction.response.send_message(embed=embed)

  #8b

@bot.tree.command(name='wisdom', description='Ask for wisdom and get an answer')
@app_commands.describe(question='The question you want to ask')
async def wisdom(interaction: discord.Interaction, question: str):
    response = random.choice(answers)
    display_name = interaction.user.display_name
    await interaction.response.send_message(f'**{display_name}** asked: {question}\n**Committee of united blacks** says: {response}')

 #spam

@bot.hybrid_command(name="spam", description="Spam a message")
async def spam(ctx: commands.Context, *, message):
    for i in range(60):
        await ctx.send(message)
        await asyncio.sleep(1)

 #forbidden gifs

@bot.tree.command(name="no-mercy", description="finish someone off")
async def strike(interaction: discord.Interaction, player: discord.Member):
    user_name = interaction.user.display_name
    player_name = player.display_name
    embed = discord.Embed(title=f"{user_name} finished {player_name}")
    image_url = "https://cdn.hentaigifz.com/20484/doggystyle001.gif"
    embed.set_image(url=image_url)
    await interaction.response.send_message(embed=embed)

 #russian roulette

spin = ["U lucky son of a ... , U SURVIVED !!!", "U live" ,"U still alive but not for long","How long do u think u can dodge that bullet","U still alive though","There is no escape the death will reach u quicker than u expect ,u still survived though","U REACHED THE END ... U DIED"]

@bot.command(name='roulette',description = 'play russian roulette')
async def rr(ctx):
    result1 = random.choice(spin)
    await ctx.send(result1)

####################################################################################################################


bot.run(os.getenv('TOKEN'))
