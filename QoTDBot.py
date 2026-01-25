from __future__ import annotations

import datetime
import os
import random
import traceback
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

import SpreadsheetAccess

load_dotenv()

THIS_FILE = Path(__file__).absolute()
ROOT_DIR = THIS_FILE.parent

# token for bot
TOKEN = os.getenv("BOTTOKEN")

# channel where QoTD will be posted every day
QOTD_CHANNEL = int(os.getenv("QOTDCHANNEL") or "0")
# channel where mods will see error messages
MODERATION_CHANNEL = int(os.getenv("MODERATIONCHANNEL") or "0")
# role that bot will ping for QoTD
ROLE_PING = os.getenv("ROLEPING")

# hour in datetime.datetime.now.hour() when the QoTD will be posted daily
POSTATHOUR = 10

def get_qotd_channel() -> (
    discord.channel.VoiceChannel
    | discord.channel.StageChannel
    | discord.channel.TextChannel
    | discord.threads.Thread
):
    """Return Question of the Day channel."""
    channel = bot.get_channel(QOTD_CHANNEL)
    if channel is None:
        raise ValueError(
            f"{QOTD_CHANNEL = } does not exist!",
        )
    if not isinstance(
        channel,
        (
            discord.channel.VoiceChannel,
            discord.channel.StageChannel,
            discord.channel.TextChannel,
            discord.threads.Thread,
        ),
    ):
        raise ValueError(
            f"{QOTD_CHANNEL = } is not the right type of channel!",
        )
    return channel


class QotdBot(commands.Bot):
    """Question of the Day Discord bot."""

    __slots__ = ("msg_sent",)

    async def on_ready(self) -> None:
        """Print message when logged in."""
        print(f"Logged on as {self.user}!")

        try:
            synced = await self.tree.sync()

            channel = get_qotd_channel()
            await self.timer.start(channel)

            print(f"Synced {len(synced)} commands.")
        except Exception as exc:
            print(f"Error syncing commands: {exc}")
            traceback.print_exception(exc)

        self.msg_sent = False

    @tasks.loop(seconds=1)
    async def timer(
        self,
        channel: (
            discord.channel.VoiceChannel
            | discord.channel.StageChannel
            | discord.channel.TextChannel
            | discord.threads.Thread
        ),
    ) -> None:
        """Timer callback to check if we need to post QOTD message."""
        current_time = datetime.datetime.now()
        if (
            current_time.hour == POSTATHOUR
            and current_time.minute == 0
            and current_time.second == 0
        ):
            if not self.msg_sent:
                await post_message(channel)
                self.msg_sent = True
        else:
            self.msg_sent = False

    async def on_message(self, message):
        if message.author == self.user:
            return
        
        if "add" in message.content.lower() and "question":
            can_use_command = message.author.guild_permissions.manage_channels
            if message.reference != None and can_use_command:

                new_question = message.reference.resolved.content
                await SpreadsheetAccess.add_unscheduled_question(new_question)
                
                await message.delete()
                await message.channel.send("Your suggestion has been added! We at Ouroboros thank you for your contribution.", reference = message.reference)


intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True
bot = QotdBot(command_prefix="!", intents=intents)

def get_moderation_channel() -> (
    discord.channel.VoiceChannel
    | discord.channel.StageChannel
    | discord.channel.TextChannel
    | discord.threads.Thread
):
    """Return moderation channel."""
    mod_channel = bot.get_channel(MODERATION_CHANNEL)
    if mod_channel is None:
        raise ValueError(
            f"{MODERATION_CHANNEL = } does not exist!",
        )
    if not isinstance(
        mod_channel,
        (
            discord.channel.VoiceChannel,
            discord.channel.StageChannel,
            discord.channel.TextChannel,
            discord.threads.Thread,
        ),
    ):
        raise ValueError(
            f"{MODERATION_CHANNEL = } is not the right type of channel!",
        )
    return mod_channel


### Post QoTD
async def post_message(
    channel: (
        discord.channel.VoiceChannel
        | discord.channel.StageChannel
        | discord.channel.TextChannel
        | discord.threads.Thread
    ),
) -> None:
    """Post the question of the day in specified channel."""
    try:

        chosen_question, question_num, questions_remaining = await SpreadsheetAccess.get_question_of_the_day()

        if chosen_question != "null":
            await channel.send(
                f" <@&{ROLE_PING}> #{question_num}\n\t\t{chosen_question}"
            )

            if questions_remaining == "null":
                mod_channel = get_moderation_channel()
                await mod_channel.send(f"There are no more Questions of the Day")
            elif questions_remaining <= 5:
                mod_channel = get_moderation_channel()
                await mod_channel.send(f"{questions_remaining} QotD left")
                
                


        else:
            mod_channel = get_moderation_channel()
            await mod_channel.send("There are no more Questions of the Day")
            


    except Exception as exc:
        mod_channel = get_moderation_channel()
        await mod_channel.send("There was an error posting the Question of The Day")
        traceback.print_exception(exc)


# Command to post a QoTD manually
def if_admin(interaction: discord.Interaction) -> bool:
    """Return if user has manage channels permission."""
    user = interaction.user
    if not isinstance(user, discord.Member):
        # Not a guild member, means direct message
        return False
    return user.guild_permissions.manage_channels


@bot.tree.command(name="forcequestion", description="Post QoTD manually")
@app_commands.check(if_admin)
async def force_question(interaction: discord.Interaction) -> None:
    """Handle force question command."""
    channel = get_qotd_channel()
    # this defer exists because of DAYS of hardship. Do no question it. Thank it for being here.
    await interaction.response.defer(ephemeral=True)
    await post_message(channel)
    await interaction.followup.send("Command Received")


# return error if user is not mod
@force_question.error
async def say_error2(interaction: discord.Interaction, error: discord.app_commands.errors.AppCommandError,) -> None:
    """Handle forcequestion command failure."""
    await interaction.response.send_message("Only administrators are allowed to manually post QoTD.", ephemeral=True)


# begins running the bot
def run() -> None:
    """Run bot."""
    if TOKEN is None:
        raise RuntimeError(
            """No token set!
Either add ".env" file in bots folder with DISCORD_TOKEN=<token here> line,
or set DISCORD_TOKEN environment variable.""",
        )
    if QOTD_CHANNEL is None:
        raise RuntimeError("No QOTDCHANNEL set")
    if MODERATION_CHANNEL is None:
        raise RuntimeError("No MODERATIONCHANNEL set")
    if ROLE_PING is None:
        raise RuntimeError("No ROLEPING set")

    # runs the bot
    bot.run(TOKEN)


if __name__ == "__main__":
    run()
