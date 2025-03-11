"""Question of the Day Bot - Discord bot for posting question of the day."""

# Question of the Day Bot - Discord bot for posting question of the day.
# MIT License
# Copyright (c) 2025 AveDonut
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

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

# file where suggestions are stored
SUGGESTIONS_PATH = ROOT_DIR / "Suggestions.txt"
# files where QoTDs will be stored while waiting to be selected
QOTD_PATH = ROOT_DIR / "QoTD.txt"
# file where past QoTDs will be stored after being used
PAST_QOTD_PATH = ROOT_DIR / "PastQoTD.txt"
# file where rejected submissions are stored
REJECTED_QOTD_PATH = ROOT_DIR / "RejectedQoTD.txt"

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


intents = discord.Intents.default()
intents.members = True
intents.guilds = True
bot = QotdBot(command_prefix="!", intents=intents)


### QoTD Submissions
@bot.tree.command(
    name="suggest",
    description="Submit suggestions for future QoTD!",
)
async def suggest(interaction: discord.Interaction, prompt: str) -> None:
    """Handle suggest command interaction."""
    try:
        with SUGGESTIONS_PATH.open("a", encoding="utf-8") as fp:
            fp.write(f"{prompt.strip()}\n")

        await interaction.response.send_message(
            "Prompt Submitted!\nYour prompt will undergo review. Keep an eye out for it in future QoTD!",
            ephemeral=True,
        )
    except Exception as exc:
        await interaction.response.send_message(
            "There was an issue receiving your submission.",
            ephemeral=True,
        )
        traceback.print_exception(exc)


### QoTD Submissions mod review
# user is considered admin if they have permission to manage channels. specific permission can be altered if needed.
def if_admin(interaction: discord.Interaction) -> bool:
    """Return if user has manage channels permission."""
    user = interaction.user
    if not isinstance(user, discord.Member):
        # Not a guild member, means direct message
        return False
    return user.guild_permissions.manage_channels


@bot.tree.command(
    name="review",
    description="Begin reviewing QoTD submissions.",
)
@app_commands.check(if_admin)
async def review(interaction: discord.Interaction) -> None:
    """Handle review command interaction."""
    await interaction.response.send_message(
        "Beginning Review...",
        ephemeral=True,
    )
    await post_submission(interaction=interaction)


# return error if user is not mod
@review.error
async def say_error(
    interaction: discord.Interaction,
    error: discord.app_commands.errors.AppCommandError,
) -> None:
    """Handle check failure for review command."""
    await interaction.response.send_message(
        "Only administrators are allowed to review QoTD submissions.",
        ephemeral=True,
    )


async def post_submission(interaction: discord.Interaction) -> None:
    """Post embed of submission to review."""
    lines = SUGGESTIONS_PATH.read_text("utf-8").splitlines()

    if lines:
        embed = discord.Embed(title=lines[0])
        embed.set_footer(text=f"{len(lines)} submissions awaiting review")
        await interaction.followup.send(
            embed=embed,
            ephemeral=True,
            view=View(),
        )
    else:
        await interaction.followup.send(
            "There are currently no submissions to review!",
            ephemeral=True,
        )


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
        lines = QOTD_PATH.read_text("utf-8").splitlines()
        chosen_question_raw = "<No questions remain>"
        if lines:
            # S311: Standard pseudo-random generators are not suitable for cryptographic purposes
            # Not using for cryptography, so it's fine.
            line_to_choose = random.randrange(len(lines))  # noqa: S311
            # pop will remove from queue
            chosen_question_raw = lines.pop(line_to_choose).strip()

        mod_channel = get_moderation_channel()
        await mod_channel.send(
            f"{len(lines)-1} Days of QoTDs remaining.",
        )

        pastlines = PAST_QOTD_PATH.read_text("utf-8").splitlines()
        question_num = len(pastlines) + 1

        # ensures the question ends with a '?' sign
        chosen_question = chosen_question_raw
        if chosen_question[-1] != "?":
            chosen_question += "?"

        # sends QoTD
        await channel.send(
            f" <@&{ROLE_PING}> #{question_num}\n\t\t{chosen_question}",
        )

        # remove QoTD from pool
        QOTD_PATH.write_text("\n".join(lines), encoding="utf-8")

        # writes QoTD to past QoTD file
        with PAST_QOTD_PATH.open("a", encoding="utf-8") as fp:
            fp.write(f"{chosen_question.strip()}\n")

    except Exception as exc:
        mod_channel = get_moderation_channel()
        await mod_channel.send(
            "There was an error posting the Question of The Day",
        )
        traceback.print_exception(exc)


# Command to post a QoTD manually
@bot.tree.command(name="forcequestion", description="Post QoTD manually")
@app_commands.check(if_admin)
async def force_question(interaction: discord.Interaction) -> None:
    """Handle force question command."""
    channel = get_qotd_channel()
    await post_message(channel)
    await interaction.response.send_message("Command received", ephemeral=True)


# return error if user is not mod
@force_question.error
async def say_error2(
    interaction: discord.Interaction,
    error: discord.app_commands.errors.AppCommandError,
) -> None:
    """Handle forcequestion command failure."""
    await interaction.response.send_message(
        "Only administrators are allowed to manually post QoTD.",
        ephemeral=True,
    )


### Review Buttons
class View(discord.ui.View):
    """Review View."""

    __slots__ = ()

    @discord.ui.button(
        label="Approve",
        style=discord.ButtonStyle.green,
        emoji="✅",
    )
    async def button_callback(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button[View],
    ) -> None:
        """Handle approve button interaction."""
        try:
            # removes suggestion from Suggestion file and appends it to QoTD file
            with open(SUGGESTIONS_PATH) as fin:
                data = fin.read().splitlines(True)
            with open(SUGGESTIONS_PATH, "w") as fout:
                fout.writelines(data[1:])

            with open(QOTD_PATH, "a") as f:
                f.write(f"{data[0].strip()}\n")

            await interaction.response.send_message(
                "Prompt Approved!",
                ephemeral=True,
            )
            await post_submission(interaction=interaction)
        except Exception as exc:
            await interaction.response.send_message(
                "Error approving prompt.",
                ephemeral=True,
            )
            traceback.print_exception(exc)

    @discord.ui.button(
        label="Reject",
        style=discord.ButtonStyle.red,
        emoji="❌",
    )
    async def button_callback_two(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button[View],
    ) -> None:
        """Handle reject button callback."""
        try:
            # removes suggestion from Suggestion file and appends it to RejectedQoTD file
            with open(SUGGESTIONS_PATH) as fin:
                data = fin.read().splitlines(True)
            with open(SUGGESTIONS_PATH, "w") as fout:
                fout.writelines(data[1:])

            with open(REJECTED_QOTD_PATH, "a") as f:
                f.write(f"{data[0].strip()}\n")

            await interaction.response.send_message(
                "Prompt Rejected!",
                ephemeral=True,
            )
            await post_submission(interaction=interaction)
        except Exception as exc:
            await interaction.response.send_message(
                "Error rejecting prompt.",
                ephemeral=True,
            )
            traceback.print_exception(exc)


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
