# K.py - Main

'''


         ,---._         ,--.
       .-- -.' \    ,--/  /|
       |    |   :,---,': / '
       :    ;   |:   : '/ /
       :        ||   '   ,
       |    :   :'   |  /
       :         |   ;  ;
       |    ;   |:   '   \
   ___ l         |   |    '
 /    /\    J   :'   : |.  \
/  ../  `..-    ,|   | '_\.'
\    \         ; '   : |
 \    \      ,'  ;   |,'
  "---....--'    '---'


'''
import discord
from discord.ext import commands
from dotenv import load_dotenv
import os

from message_with_channel_id import message_with_channel_id

load_dotenv()

# .env
TOKEN = os.getenv("DISCORD_TOKEN")

# Permission
intents = discord.Intents.all()
# command - 정의
bot = commands.Bot(command_prefix='!', intents=intents)

# modules
message_with_channel_id(bot)

# onEnable
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

#running - jk
bot.run(TOKEN)
