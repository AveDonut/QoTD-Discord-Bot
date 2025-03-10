import discord
from discord.ext import commands, tasks
from discord import app_commands

import random

import time
import datetime
time = datetime.datetime.now

import os
from dotenv import load_dotenv

load_dotenv()

BOTTOKEN = os.getenv("BOTTOKEN") # token for bot

QOTDCHANNEL = os.getenv("QOTDCHANNEL") # channel where QoTD will be posted every day
MODERATIONCHANNEL = os.getenv("MODERATIONCHANNEL") # channel where mods will see error messages
GUILD_ID = discord.Object(id=os.getenv("GUILD_ID")) # Guild where bot will be implemented
ROLEPING = os.getenv("ROLEPING") # role that bot will ping for QoTD

SUGGESTEDFILE = "Suggestions.txt" # file where suggestions are stored
QOTDFILE = "QoTD.txt" # files where QoTDs will be stored while waiting to be selected
PASTQOTDFILE = "PastQoTD.txt" # file where past QoTDs will be stored after being used
REJECTEDQOTDFILE = "RejectedQoTD.txt" # file where rejected submissions are stored

POSTATHOUR = 10 # hour in time.hour() when the QoTD will be posted daily


class Client(commands.Bot):
    async def on_ready(self):
        # prints message when logged in
        print(f'Logged on as {self.user}!')
        
        try:
            synced = await self.tree.sync(guild=GUILD_ID)

            channel = bot.get_channel(QOTDCHANNEL)
            await self.timer.start(channel)

            print(f'Synced {len(synced)} commands to guild {GUILD_ID.id}')
        except Exception as e:
            print(f'error syncing commands: {e}')
            
    @tasks.loop(seconds=1)
    async def timer(self, channel):
        if time().hour == POSTATHOUR and time().minute == 0 and time().second == 0:
            if not self.msg_sent:
                await post_message(channel)
                self.msg_sent = True
        else:
            self.msg_sent = False


intents = discord.Intents.default()
intents.members = True
intents.guilds = True
bot = Client(command_prefix="!", intents=intents)

### QoTD Submissions
@bot.tree.command(name="suggest",description="Submit suggestions for future QoTD!", guild=GUILD_ID)
async def suggest(interaction: discord.Interaction, prompt: str) -> None:
    try:
        with open(SUGGESTEDFILE, 'a') as f:
            f.write(f'{prompt.strip()}\n')
        
        await interaction.response.send_message("Prompt Submitted!\nYour prompt will undergo review. Keep an eye out for it in future QoTD!", ephemeral=True)
    except:
        await interaction.response.send_message("There was an issue recieving your submission.", ephemeral=True)


### QoTD Submissions mod review
# user is considered admin if they have permission to manage channels. specific permission can be altered if needed.
def if_admin(interaction: discord.Interaction):
    return interaction.user.guild_permissions.manage_channels == True

@bot.tree.command(name="review",description="Begin reviewing QoTD submissions.", guild=GUILD_ID)
@app_commands.check(if_admin)
async def Review(interaction: discord.Interaction) -> None:
    await interaction.response.send_message("Beginning Review...", ephemeral=True)
    await PostSubmission(interaction=interaction)

# return error if user is not mod
@Review.error
async def say_error(interaction: discord.Interaction, error):
    await interaction.response.send_message("Only administators are allowed to review QoTD submissions.", ephemeral=True)

# posts embed of submission to review
async def PostSubmission(interaction: discord.Interaction) -> None:
    with open(SUGGESTEDFILE, 'r') as f:
        lines = f.readlines()

        if not lines == []:
            embed = discord.Embed(title=lines[0])
            embed.set_footer(text=f'{len(lines)} submissions awaiting review')
            await interaction.followup.send(embed=embed, ephemeral=True, view=View())
        else:
            await interaction.followup.send("There are currently no submissions to review!", ephemeral=True)

### Post QoTD
async def post_message(channel):
    try:
        with open(QOTDFILE, 'r', errors="ignore") as f:
            lines = f.readlines()
            if not lines == []:
                line_to_choose = random.randint(0,len(lines)-1)
                chose_question_raw = lines[line_to_choose]
            
            
            if len(lines) == 8:
                await bot.get_channel(MODERATIONCHANNEL).send("7 Days of QoTDs remaining.")

        
        with open(PASTQOTDFILE, 'r') as f:
            pastlines = f.readlines()
            question_num = len(pastlines) + 1

        # ensures the question ends with a ?
        if not chose_question_raw.strip()[-1] == "?":
            chose_question = chose_question_raw.strip() + "?"
        else:
            chose_question = chose_question_raw.strip()
        
        # sends QoTD
        await channel.send(f' <@&{ROLEPING}> #{question_num}\n\t\t{chose_question}')

        # removes QoTD from pool
        with open(QOTDFILE, 'w') as f:
            for line in lines:
                if line != chose_question_raw:
                    f.write(line)
        
        # writes QoTD to past QoTD file
        with open(PASTQOTDFILE, 'a') as f:
            f.write(f'{chose_question.strip()}\n')
        
    except:
        await bot.get_channel(MODERATIONCHANNEL).send("There was an error posting the Question of The Day")
    

# Command to post a QoTD manually
@bot.tree.command(name="forcequestion",description="Post QoTD manually", guild=GUILD_ID)
@app_commands.check(if_admin)
async def ForceQoTD(interaction: discord.Interaction) -> None:
    channel = bot.get_channel(QOTDCHANNEL)
    await post_message(channel)
    await interaction.response.send_message("Command recieved", ephemeral=True)

# return error if user is not mod
@ForceQoTD.error
async def say_error2(interaction: discord.Interaction, error):
    await interaction.response.send_message("Only administators are allowed to manually post QoTD.", ephemeral=True)


### Review Buttons
class View(discord.ui.View):
    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, emoji="✅")
    async def button_callback(self, button, interaction):
        try:
            # removes suggestion from Suggestion file and appends it to QoTD file
            with open(SUGGESTEDFILE, 'r') as fin:
                data = fin.read().splitlines(True)
            with open(SUGGESTEDFILE, 'w') as fout:
                fout.writelines(data[1:])
                
            with open(QOTDFILE, 'a') as f:
                f.write(f'{data[0].strip()}\n')
                
            await button.response.send_message("Prompt Approved!", ephemeral=True)
            await PostSubmission(interaction=button)
        except:
            await button.response.send_message("Error approving prompt.", ephemeral=True)
            

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.red, emoji="❌")
    async def button_callback_two(self, button, interaction):
        try:
            # removes suggestion from Suggestion file and appends it to RejectedQoTD file
            with open(SUGGESTEDFILE, 'r') as fin:
                data = fin.read().splitlines(True)
            with open(SUGGESTEDFILE, 'w') as fout:
                fout.writelines(data[1:])
                
            with open(REJECTEDQOTDFILE, 'a') as f:
                f.write(f'{data[0].strip()}\n')
                
            await button.response.send_message("Prompt Rejected!", ephemeral=True)
            await PostSubmission(interaction=button)
        except:
            await button.response.send_message("Error rejecting prompt.", ephemeral=True)

# runs the bot
bot.run(BOTTOKEN)