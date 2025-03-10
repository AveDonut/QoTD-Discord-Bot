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
QOTD_CHANNEL = os.getenv("QOTDCHANNEL")
# channel where mods will see error messages
MODERATION_CHANNEL = os.getenv("MODERATIONCHANNEL")
# role that bot will ping for QoTD
ROLEPING = os.getenv("ROLEPING")

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


class QotdBot(commands.Bot):
    """Question of the Day Discord bot."""

    __slots__ = ()

    async def on_ready(self) -> None:
        """Print message when logged in."""
        print(f"Logged on as {self.user}!")

        try:
            synced = await self.tree.sync()

            channel = bot.get_channel(QOTD_CHANNEL)
            await self.timer.start(channel)

            print(f"Synced {len(synced)} commands.")
        except Exception as exc:
            print(f"Error syncing commands: {exc}")
            traceback.print_exception(exc)

    @tasks.loop(seconds=1)
    async def timer(self, channel):
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
    try:
        with open(SUGGESTIONS_PATH, "a") as f:
            f.write(f"{prompt.strip()}\n")

        await interaction.response.send_message(
            "Prompt Submitted!\nYour prompt will undergo review. Keep an eye out for it in future QoTD!",
            ephemeral=True,
        )
    except:
        await interaction.response.send_message(
            "There was an issue receiving your submission.",
            ephemeral=True,
        )


### QoTD Submissions mod review
# user is considered admin if they have permission to manage channels. specific permission can be altered if needed.
def if_admin(interaction: discord.Interaction):
    return interaction.user.guild_permissions.manage_channels is True


@bot.tree.command(
    name="review",
    description="Begin reviewing QoTD submissions.",
)
@app_commands.check(if_admin)
async def Review(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(
        "Beginning Review...",
        ephemeral=True,
    )
    await PostSubmission(interaction=interaction)


# return error if user is not mod
@Review.error
async def say_error(interaction: discord.Interaction, error):
    await interaction.response.send_message(
        "Only administrators are allowed to review QoTD submissions.",
        ephemeral=True,
    )


# posts embed of submission to review
async def PostSubmission(interaction: discord.Interaction) -> None:
    with open(SUGGESTIONS_PATH) as f:
        lines = f.readlines()

        if lines != []:
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


### Post QoTD
async def post_message(
    channel: (
        discord.channel.VoiceChannel
        | discord.channel.StageChannel
        | discord.channel.ForumChannel
        | discord.channel.TextChannel
        | discord.channel.CategoryChannel
        | discord.threads.Thread
        | discord.abc.PrivateChannel
        | None
    ),
) -> None:
    try:
        with open(QOTD_PATH, errors="ignore") as f:
            lines = f.readlines()
            if lines != []:
                line_to_choose = random.randint(0, len(lines) - 1)
                chose_question_raw = lines[line_to_choose]

            if len(lines) == 8:
                await bot.get_channel(MODERATION_CHANNEL).send(
                    "7 Days of QoTDs remaining.",
                )

        with open(PAST_QOTD_PATH) as f:
            pastlines = f.readlines()
            question_num = len(pastlines) + 1

        # ensures the question ends with a ?
        if chose_question_raw.strip()[-1] != "?":
            chose_question = chose_question_raw.strip() + "?"
        else:
            chose_question = chose_question_raw.strip()

        # sends QoTD
        await channel.send(
            f" <@&{ROLEPING}> #{question_num}\n\t\t{chose_question}",
        )

        # removes QoTD from pool
        with open(QOTD_PATH, "w") as f:
            for line in lines:
                if line != chose_question_raw:
                    f.write(line)

        # writes QoTD to past QoTD file
        with open(PAST_QOTD_PATH, "a") as f:
            f.write(f"{chose_question.strip()}\n")

    except:
        await bot.get_channel(MODERATION_CHANNEL).send(
            "There was an error posting the Question of The Day",
        )


# Command to post a QoTD manually
@bot.tree.command(name="forcequestion", description="Post QoTD manually")
@app_commands.check(if_admin)
async def ForceQoTD(interaction: discord.Interaction) -> None:
    channel = bot.get_channel(QOTD_CHANNEL)
    await post_message(channel)
    await interaction.response.send_message("Command received", ephemeral=True)


# return error if user is not mod
@ForceQoTD.error
async def say_error2(interaction: discord.Interaction, error):
    await interaction.response.send_message(
        "Only administrators are allowed to manually post QoTD.",
        ephemeral=True,
    )


### Review Buttons
class View(discord.ui.View):
    @discord.ui.button(
        label="Approve",
        style=discord.ButtonStyle.green,
        emoji="✅",
    )
    async def button_callback(self, button, interaction):
        try:
            # removes suggestion from Suggestion file and appends it to QoTD file
            with open(SUGGESTIONS_PATH) as fin:
                data = fin.read().splitlines(True)
            with open(SUGGESTIONS_PATH, "w") as fout:
                fout.writelines(data[1:])

            with open(QOTD_PATH, "a") as f:
                f.write(f"{data[0].strip()}\n")

            await button.response.send_message(
                "Prompt Approved!",
                ephemeral=True,
            )
            await PostSubmission(interaction=button)
        except:
            await button.response.send_message(
                "Error approving prompt.",
                ephemeral=True,
            )

    @discord.ui.button(
        label="Reject",
        style=discord.ButtonStyle.red,
        emoji="❌",
    )
    async def button_callback_two(self, button, interaction):
        try:
            # removes suggestion from Suggestion file and appends it to RejectedQoTD file
            with open(SUGGESTIONS_PATH) as fin:
                data = fin.read().splitlines(True)
            with open(SUGGESTIONS_PATH, "w") as fout:
                fout.writelines(data[1:])

            with open(REJECTED_QOTD_PATH, "a") as f:
                f.write(f"{data[0].strip()}\n")

            await button.response.send_message(
                "Prompt Rejected!",
                ephemeral=True,
            )
            await PostSubmission(interaction=button)
        except:
            await button.response.send_message(
                "Error rejecting prompt.",
                ephemeral=True,
            )


def run() -> None:
    """Run bot."""
    if TOKEN is None:
        raise RuntimeError(
            """No token set!
Either add ".env" file in bots folder with DISCORD_TOKEN=<token here> line,
or set DISCORD_TOKEN environment variable.""",
        )

    # runs the bot
    bot.run(TOKEN)


if __name__ == "__main__":
    run()
