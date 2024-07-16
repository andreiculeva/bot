import contextlib
import io
import os
import pathlib
import matplotlib
import pkg_resources
import utils
from io import BytesIO
import typing
import discord
from discord.errors import HTTPException, NotFound
from discord.ext import commands
from discord.ext.commands.converter import PartialEmojiConverter
import datetime
import time
import re
import asyncio
import unicodedata
import pytube
import humanfriendly
import matplotlib.pyplot as plt
import bot
from discord import app_commands
import yt_dlp
import contextlib
import importlib

# from whenareyou import whenareyou
import pytz
import psutil
import sys
import lavalink

inv = (discord.Status.invisible, discord.Status.offline)


activity_em = {
    "idle": "<:idle:1002554573896028382>",
    "dnd": "<:dnd:1002554551959818291>",
    "offline": "<:offline:1002554608201257060>",
    "online": "<:online:1002554648634347640>",
}


class CustomTimeConverter(commands.Converter):
    async def convert(
        self, ctx: commands.Context[bot.AndreiBot], argument: str
    ) -> datetime.datetime:
        rx = re.compile(r"([0-9]{15,20})$")
        if rx.match(argument):
            return discord.utils.snowflake_time(int(argument))
        date_arguments = argument.split("/")
        if len(date_arguments) == 2:
            day, month = date_arguments
            year = datetime.date.today().year
        elif len(date_arguments) == 3:
            day, month, year = date_arguments
        else:
            raise commands.BadArgument(
                f"'{argument}' is not a valid date argument or snowflake time"
            )  # god fucking knows
        day, month, year = int(day), int(month), int(year)
        return datetime.datetime(year, month, day, tzinfo=datetime.timezone.utc)


class ProfileView(discord.ui.View):
    async def on_timeout(self) -> None:
        if self.message:
            await self.message.edit(view=None)


def get_member_perms(member: discord.Member) -> tuple[str]:
    to_clean = (
        "add_reactions",
        "attach_files",
        "change_nickname",
        "connect",
        "create_instant_invite",
        "create_private_threads",
        "create_public_threads",
        "deafen_members",
        "embed_links",
        "external_emojis",
        "external_stickers",
        "manage_threads",
        "manage_webhooks",
        "use_voice_activation",
        "view_audit_log",
        "priority_speaker",
        "read_message_history",
        "request_to_speak",
        "send_messages_in_threads",
        "send_tts_messages",
        "speak",
        "stream",
        "view_guild_insights",
        "read_messages",
        "use_application_commands",
        "send_messages",
        "use_embedded_activities",
    )
    clean_perms: list[str] = []
    for name, value in member.guild_permissions:
        if (not (name in to_clean)) and value:
            clean_perms.append(name)
    if member == member.guild.owner:
        member_perms = ["Server Owner"]
    elif member.guild_permissions.administrator:
        member_perms = ["Administrator"]
    else:
        member_perms = [perm.title().replace("_", " ") for perm in clean_perms]
        member_perms.sort()
        member_perms = [k.replace("Guild", "Server") for k in member_perms]
        member_perms = tuple(f"`{k}`" for k in member_perms)
    return member_perms


def get_str_time(seconds) -> str:
    if seconds == 0:
        return ""
    delta = datetime.timedelta(seconds=seconds)
    return humanfriendly.format_timespan(delta, max_units=2)


class StickerModal(discord.ui.Modal):

    name = discord.ui.TextInput(label="name", style=discord.TextStyle.short)
    description = discord.ui.TextInput(
        label="description", style=discord.TextStyle.long
    )

    def __init__(self, view: discord.ui.View) -> None:
        super().__init__(title="Make a sticker")
        self.view = view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.view.stop()
        await interaction.response.defer(ephemeral=True)


class StickerView(discord.ui.View):
    def __init__(
        self, author: discord.Member, *, timeout: typing.Optional[float] = 180
    ):
        super().__init__(timeout=600)
        self.author = author
        self.value: typing.Literal[1, 2, 3] = None
        self.modal = StickerModal(view=self)

    @discord.ui.button(label="existing sticker")
    async def existing_sticker(self, interaction: discord.Interaction, _):
        self.value = 1
        await interaction.response.send_modal(self.modal)

    @discord.ui.button(label="from file")
    async def from_file(self, interaction: discord.Interaction, _):
        self.value = 2
        await interaction.response.send_modal(self.modal)

    @discord.ui.button(label="image url", disabled=True)
    async def from_url(self, interaction: discord.Interaction, _):
        self.value = 3
        self.interaction = interaction

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.author:
            return True
        await interaction.response.send_message(
            "You can't use this button", ephemeral=True
        )
        return False


red = discord.Color.red()
orange = discord.Color.orange()


class Utility(commands.Cog):
    """chat commands with prefix"""

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(name="\N{BAR CHART}")

    def __init__(self, _bot):
        self.bot: bot.AndreiBot = _bot

    @commands.hybrid_command(description="Shows the bot latency")
    async def ping(self, ctx: commands.Context):
        async def measure_ping(coro) -> float:
            start = time.monotonic()
            await coro
            return time.monotonic() - start

        db = await measure_ping(
            self.bot.pool.fetchrow("SELECT * FROM internal_config LIMIT 1")
        )
        http_request = await measure_ping(ctx.typing())
        embed = discord.Embed(color=discord.Color.orange(), title="Ping")
        embed.add_field(
            name="Discord Websocket", value=f"`{self.bot.latency * 1000:.2f}`ms"
        )
        embed.add_field(name="Database", value=f"`{db * 1000:.2f}`ms")
        embed.add_field(name="HTTP request", value=f"`{http_request * 1000:.2f}`ms")
        await ctx.send(embed=embed)

    @commands.command()
    async def snipe(
        self,
        ctx: commands.Context,
        user: typing.Optional[discord.User] = None,
        offset=None,
    ):
        """Used to show deleted messages.
        `offset`: how far to search.
        `user`: will only search for messages from that user.
        Deleted files are stored in RAM for only 1 hour"""
        if offset is not None:
            try:
                offset = int(offset) - 1
            except ValueError:
                em = discord.Embed(color=red)
                em.description = "please enter a valid number"
                await ctx.send(embed=em)
                return
        else:
            offset = 0
        if user is not None:
            request = f"SELECT * FROM deleted_messages WHERE channel_id = {ctx.channel.id} AND author_id = {user.id} ORDER BY datetime DESC LIMIT 1 OFFSET {offset}"
        else:
            request = f"SELECT * FROM deleted_messages WHERE channel_id = {ctx.channel.id} ORDER BY datetime DESC LIMIT 1 OFFSET {offset}"
        res = await self.bot.pool.fetchrow(request)
        if not res:
            em = discord.Embed(color=red)
            em.description = "I couldn't find anything"
            return await ctx.send(embed=em)
        data = res
        em = discord.Embed(color=orange)
        if data["reference_message_id"]:
            _message_id = data["reference_message_id"]
            _message = self.bot._connection._get_message(_message_id)
            if _message is None:
                try:
                    _message = await ctx.channel.fetch_message(_message_id)
                except (discord.HTTPException, discord.NotFound):
                    _message = None
            _user = self.bot.get_user(data["reference_author_id"])
            if _user is None:
                # this should always return something
                _user = await self.bot.fetch_user(data["reference_author_id"])
            em.title = f"replying to {_user}"
            if _message:
                em.url = _message.jump_url
        em.description = data["message_content"]  # message content
        em.timestamp = data["datetime"]
        m = self.bot.get_user(int(data["author_id"]))
        if m:
            em.set_author(name=m, icon_url=m.display_avatar)
        v = utils.DeletedView(
            bot=self.bot, ctx=ctx, message_id=data["message_id"], author=m
        )
        v.message = await ctx.send(embed=em, view=v)

    @commands.hybrid_command(aliases=["memberinfo", "userinfo", "whois"])
    @app_commands.describe(user="The target user")
    async def profile(
        self,
        ctx: commands.Context,
        user: typing.Annotated[discord.User, utils.CustomUserTransformer] = None,
    ):
        "Shows useful info about a discord user"

        if user is None:
            user = await utils.get_reference(ctx.message)
        if user is None:
            user = ctx.author

        view = ProfileView(timeout=600)
        view.message: discord.Message = None  # type: ignore
        member = ctx.guild.get_member(user.id)
        fetched_user = await self.bot.fetch_user(user.id)
        banner = fetched_user.banner

        embed = discord.Embed(
            color=fetched_user.accent_color or discord.Color.orange(),
            description="",
        )
        if user != self.bot.user and user.mutual_guilds:
            embed.description += f"We share {len(user.mutual_guilds)} servers"
        embed.description += (
            f"\naccount created {discord.utils.format_dt(user.created_at, style='R')}"
        )
        embed.set_author(name=user, icon_url=user.display_avatar)
        embed.set_footer(text=f"ID: {user.id}")
        val = f"[avatar]({fetched_user.display_avatar})"

        if member:
            if member.guild_avatar:
                val += f"\n[server avatar]({member.guild_avatar})"
            embed.description += (
                f"\njoined {discord.utils.format_dt(member.joined_at, style='R')}"
            )

            if member.mobile_status not in (inv):
                embed.description += f"\n\U0001f4f1 on mobile"
            if member.desktop_status not in (inv):
                embed.description += f"\n\U0001f5a5 on desktop client"
            if member.web_status not in (inv):
                embed.description += "\n\U0001f4bb on browser client"
            if member.premium_since:
                embed.description += f"\n{utils.profile_emojis.get('nitro')} boosting this server since {discord.utils.format_dt(member.premium_since, style='R')}"
            view.add_item(utils.PermsButton(member=member, row=len(view.children) // 3))
            view.add_item(utils.RolesButton(member=member, row=len(view.children) // 3))




        if banner:
            val += f"\n[banner]({banner})"

        if user.public_flags:
            val1 = ""
            count = 0
            for flag in user.public_flags.all():
                a = "\n"
                val1 += f"{' ' if count%3 else a}{utils.profile_emojis.get(flag.name, flag.name.replace('_', ' '))}"
                count += 1
            if val1:
                embed.add_field(name=f"badges", value=val1)

        embed.add_field(name="urls", value=val)

        if await self.bot.pool.fetchrow(
            "SELECT * FROM nicknames WHERE user_id = $1 AND server_id = $2 ORDER BY datetime DESC",
            user.id,
            ctx.guild.id,
        ):
            view.add_item(
                utils.NicknamesButton(member=user, row=len(view.children) // 3)
            )
        if await self.bot.pool.fetchrow(
            f"SELECT * FROM usernames WHERE user_id = {user.id}"
        ):
            view.add_item(utils.UsernamesButton(user=user, row=len(view.children) // 3))
        view.add_item(utils.url_button(user, row=len(view.children) // 3))

        if ctx.interaction:
            await ctx.send(embed=embed, view=view)
            view.message = await ctx.interaction.original_response()
        else:
            view.message = await ctx.send(embed=embed, view=view)

    @commands.command(aliases=["av"])
    async def avatar(self, ctx: commands.Context, user: utils.UserConverter = None):
        """Returns the `user`'s avatar.
        `user` can be the message reference's author.
        `user` can be any discord user."""
        if user is None:
            user = await utils.get_reference(ctx.message)
        if user is None:
            user = ctx.author

        em = discord.Embed(color=orange)
        em.set_author(name=user, icon_url=user.display_avatar)
        em.set_image(url=user.avatar)
        return await ctx.send(
            embed=em, view=discord.ui.View().add_item(utils.url_button(user))
        )

    @commands.command(aliases=["sav", "serveravatar"])
    async def savatar(
        self, ctx: commands.Context, member: utils.MemberConverter = None
    ):
        """Returns the `member`'s server avatar, if available.
        `member` can be the author of the message reference"""

        if member is None:
            member = await utils.get_member_reference(ctx.message)
        if member is None:
            member = ctx.author

        if member.guild_avatar is None:
            return await ctx.send("This member has no server avatar")
        em = discord.Embed(color=red)
        em.set_author(name=member, icon_url=member.guild_avatar)
        return await ctx.send(
            embed=em, view=discord.ui.View().add_item(utils.url_button(member))
        )

    @commands.command()
    async def banner(
        self,
        ctx: commands.Context,
        user: typing.Annotated[discord.User, utils.CustomUserTransformer] = None,
    ):
        """View any discord user's banner"""
        if user is None:
            user = await utils.get_reference(ctx.message)
        if user is None:
            user = ctx.author
        us = await self.bot.fetch_user(user.id)  # should never error
        if us.banner is None:
            raise commands.CommandInvokeError(f"{us} has no banner")
        em = discord.Embed(color=discord.Color.orange())
        em.set_author(name=us, icon_url=us.display_avatar)
        em.set_image(url=us.banner)
        await ctx.send(embed=em)

    @commands.group(invoke_without_command=True, aliases=["emote"])
    async def emoji(self, ctx: commands.Context):
        """Sends emoji help command"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help("emoji")

    @emoji.command(aliases=["show"])
    async def info(self, ctx: commands.Context, emoji: discord.PartialEmoji):
        """Shows info about any discord `emoji`"""
        emoji_str = "<"
        if emoji.animated:
            emoji_str += "a"
        emoji_str += f":{emoji.name}:"
        emoji_str += f"{emoji.id}>"
        em = discord.Embed(
            color=orange,
            description=f"name: {emoji.name}\nID: {emoji.id}\nanimated: {emoji.animated}\n`{emoji_str}`\n[EMOJI URL]({emoji.url})",
        )
        em.set_thumbnail(url=emoji.url)
        view = utils.EmojiView(emoji)
        view.message = await ctx.send(embed=em, view=view)

    @commands.has_guild_permissions(manage_emojis=True)
    @emoji.command(aliases=["create", "clone", "copy"])
    async def add(self, ctx: commands.Context, emoji, *, name: str = None):
        """Adds `emoji` to the server\n`emoji` can be an image URL, `name` will be required in that case"""
        try:
            _emoji = await PartialEmojiConverter().convert(ctx, emoji)
            emoji_url = _emoji.url
            name = name or _emoji.name
        except commands.PartialEmojiConversionFailure:
            if not re.match(
                "http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
                emoji,
            ):
                em = discord.Embed(color=discord.Color.red())
                em.description = "That's not a valid emoji or URL"
                return await ctx.send(embed=em)
            emoji_url = emoji
        if name is None:
            em = discord.Embed(
                color=discord.Color.red(),
                description=f"`name` is a required argument that is missing <:meh:854231053124370482>",
            )
            return await ctx.send(embed=em)
        name = name.replace(" ", "_")
        emoji_url = emoji_url.replace(".webp", ".png")

        async with self.bot.session.get(emoji_url) as r:
            image_bytes = await r.read()
        new_emoji = await ctx.guild.create_custom_emoji(name=name, image=image_bytes)
        em = discord.Embed(
            color=discord.Color.green(),
            description=f"done {new_emoji}\nname: {new_emoji.name}\nID: {new_emoji.id}\nanimated: {new_emoji.animated}\n`{new_emoji}`",
        )
        em.set_thumbnail(url=new_emoji.url)
        await ctx.send(embed=em)

    @emoji.command(aliases=["remove"])
    async def delete(self, ctx: commands.Context, emoji: discord.Emoji):
        """Deletes the `emoji`, if the bot can see it"""
        _author = emoji.guild.get_member(ctx.author.id)
        if _author is None:
            em = discord.Embed(
                color=discord.Color.red(), description="You're not in that server"
            )
            return await ctx.send(embed=em)
        if not _author.guild_permissions.manage_emojis:
            em = discord.Embed(
                color=discord.Color.red(),
                description=f"You are missing the `manage emojis` permission in {emoji.guild.name}",
            )
            return await ctx.send(embed=em)
        if not _author.guild.me.guild_permissions.manage_emojis:
            em = discord.Embed(
                color=discord.Color.red(),
                description=f"I am missing the `manage emojis` permission in {emoji.guild.name}",
            )
            return await ctx.send(embed=em)
        view = utils.ConfirmationDeleteView(ctx, emoji)
        view.message = await ctx.send(
            embed=discord.Embed(
                color=orange, description=f"Are you sure you want to delete {emoji}?"
            ),
            view=view,
        )

    @emoji.command(name="edit")
    async def edit(self, ctx: commands.Context, emoji: discord.Emoji, *, name: str):
        """Edits the `emoji`'s name, if the bot can see it"""
        _author = emoji.guild.get_member(ctx.author.id)
        if _author is None:
            em = discord.Embed(
                color=discord.Color.red(), description="You're not in that server"
            )
            return await ctx.send(embed=em)
        if not _author.guild_permissions.manage_emojis:
            em = discord.Embed(
                color=discord.Color.red(),
                description=f"You are missing the `manage emojis` permission in {emoji.guild.name}",
            )
            return await ctx.send(embed=em)
        if not _author.guild.me.guild_permissions.manage_emojis:
            em = discord.Embed(
                color=discord.Color.red(),
                description=f"I am missing the `manage emojis` permission in {emoji.guild.name}",
            )
            return await ctx.send(embed=em)
        name = name.replace(" ", "_")
        try:
            await emoji.edit(
                name=name,
                reason=f"{ctx.author} changed name from {emoji.name} to {name}",
            )
        except discord.HTTPException as e:
            em = discord.Embed(color=discord.Color.red(), description=e)
        await ctx.message.add_reaction("\U0001f44d")

    @emoji.command(aliases=["reactions"])
    async def reaction(
        self, ctx: commands.Context, message: discord.PartialMessage = None
    ):
        """Shows the emojis of a message's reactions.
        message can be `channelID-messageID`, `messageID` (in the same channel), message URL or just a reply to that message
        """
        try:
            if message is None:
                if ctx.message.reference is None:
                    raise commands.MissingRequiredArgument("message")
                mes = await ctx.fetch_message(ctx.message.reference.message_id)
            else:
                mes = await message.fetch()
        except (NotFound, HTTPException):
            return await ctx.send("I couldn't find that message")
        if not mes.reactions:
            return await ctx.send("This message has no reactions")
        emojis: list[typing.Union[discord.Emoji, discord.PartialEmoji]] = [
            m.emoji
            for m in mes.reactions
            if isinstance(m.emoji, (discord.Emoji, discord.PartialEmoji))
        ]
        if not emojis:
            return await ctx.send("This message has no custom emojis")
        source = utils.EmojiPageSource(emojis, per_page=1)
        pages = utils.EmojiPages(
            source, client=self.bot, author=ctx.author, channel=ctx.channel, search=True
        )
        await pages.start()

    @commands.hybrid_group()
    @app_commands.default_permissions(administrator=True)
    @commands.has_guild_permissions(administrator=True)
    async def prefix(self, ctx: commands.Context):
        """Manages the bot's prefixes, use help prefix for subcommands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @prefix.command()
    @app_commands.describe(prefix="the new prefix")
    async def set(self, ctx: commands.Context[bot.AndreiBot], *, prefix: str):
        """Sets or edits the bot's prefix for this server"""
        await self.bot.pool.execute(
            "INSERT INTO server_prefixes (server_id, prefix) VALUES ($1, $2) ON CONFLICT (server_id) DO UPDATE SET prefix=excluded.prefix",
            ctx.guild.id,
            prefix,
        )
        em = discord.Embed(
            color=orange, description=f"Prefix set to `{prefix}` for this server"
        )
        await ctx.send(embed=em, mention_author=False)
        await ctx.bot.update_prefixes()

    @prefix.command()
    async def remove(self, ctx: commands.Context[bot.AndreiBot]):
        """Removes the bot's prefix from this server"""
        await self.bot.pool.execute(
            "DELETE FROM server_prefixes WHERE server_id=$1", ctx.guild.id
        )
        if ctx.interaction:
            await ctx.send("\U0001f44d", ephemeral=True)
        else:
            await ctx.message.add_reaction("\U0001f44d")
        await ctx.bot.update_prefixes()

    @commands.command()
    async def charinfo(self, ctx, *, characters: str):
        """Shows you information about a number of characters.
        Only up to 25 characters at a time.
        """

        def to_string(c):
            digit = f"{ord(c):x}"
            name = unicodedata.name(c, "Name not found.")
            return f"`\\U{digit:>08}`: {name} - {c} \N{EM DASH} <http://www.fileformat.info/info/unicode/char/{digit}>"

        msg = "\n".join(map(to_string, characters))
        if len(msg) > 2000:
            return await ctx.send("Output too long to display.")
        await ctx.send(msg)

    @commands.hybrid_command()
    @app_commands.describe(role="The target role")
    async def inrole(
        self,
        ctx: commands.Context,
        role: typing.Annotated[discord.Role, utils.CustomRoleTransformer],
    ):
        """Returns all the users in the specified role."""
        if len(role.members) == 0:
            return await ctx.send(
                embed=discord.Embed(color=red, description="No users have that role")
            )

        def sortfunc(m: discord.Member):
            return m.name.lower()

        sorted_list = role.members
        sorted_list.sort(key=sortfunc)
        new_list = []
        for member in sorted_list:
            name = member.name
            new_name = ""
            for character in name:
                if character in ("*", "_", "|", "~", "`"):
                    new_name += chr(92) + character
                else:
                    new_name += character
            new_list.append(f"{new_name}#{member.discriminator}")
        pages = utils.RolePages(entries=new_list, ctx=ctx, role=role)
        await pages.start()

    @commands.command(aliases=["esnipe", "es"])
    async def editsnipe(self, ctx: commands.Context, messages=None):
        """Searches message edits in the database.
        `messages`: how far to search through.
        Works with a message reply too."""

        if (ctx.message.reference is None) and (messages is None):  # search one only
            firstquer = f"SELECT message_id, datetime FROM edited_messages WHERE channel_id = {ctx.channel.id} ORDER BY datetime DESC LIMIT 1"
            message_id = await self.bot.pool.fetchval(firstquer)
            if not message_id:
                return await ctx.send(
                    embed=discord.Embed(
                        color=red, description="I couldn't find anything"
                    )
                )
            query = f"SELECT message_content, datetime, author_id FROM edited_messages WHERE message_id = {message_id} ORDER BY datetime ASC"
        elif messages is not None:  # offset
            try:
                messages = int(messages) - 1
            except ValueError:
                return await ctx.send(
                    embed=discord.Embed(
                        color=red, description=f"`{messages}` is an invalid number"
                    )
                )
            firstquer = f"SELECT DISTINCT message_id, datetime FROM edited_messages WHERE channel_id = {ctx.channel.id} ORDER BY datetime DESC LIMIT 1 OFFSET {messages}"
            message_id = await self.bot.pool.fetchval(firstquer)
            if not message_id:
                return await ctx.send(
                    embed=discord.Embed(
                        color=red, description="I couldn't find anything"
                    )
                )
            query = f"SELECT message_content, datetime, author_id FROM edited_messages WHERE message_id = {message_id} ORDER BY datetime ASC"
        else:  # magic reference lookup - ctx.reference should always exist
            message_id = ctx.message.reference.message_id
            query = f"SELECT message_content, datetime, author_id FROM edited_messages WHERE message_id = {message_id} ORDER BY datetime ASC"

        allmessages = await self.bot.pool.fetch(query)
        if not allmessages:
            return await ctx.send(
                embed=discord.Embed(color=red, description="I couldn't find anything")
            )
        edits = allmessages[1:]
        # edits = [] #list of all edits [(content, timestamp, author), ...]
        original: tuple = allmessages[0]
        author = self.bot.get_user(int(original["author_id"]))
        if author is None:
            try:
                author = await self.bot.fetch_user(int(original["author_id"]))
            except (discord.NotFound, discord.HTTPException):
                author = None
        pages = utils.SnipeSimplePages(
            entries=edits, ctx=ctx, original=original, author=author
        )
        await pages.start()

    @commands.hybrid_command()
    async def members(self, ctx: commands.Context):
        """Shows members in the server, ordered by their join date"""
        entries = [
            f"{discord.utils.format_dt(k.joined_at, 'd')} {k.mention}"
            for k in sorted(
                [m for m in ctx.guild.members if (not m.bot)], key=lambda x: x.joined_at
            )
        ]
        pages = utils.SimplePages(
            entries=entries,
            ctx=ctx,
            title="members",
            description="ordered by join date",
        )
        await pages.start()

    @commands.has_guild_permissions(administrator=True)
    @commands.command()
    async def invitelog(
        self, ctx: commands.Context, channel: discord.TextChannel = None
    ):
        """Sets the channel to log invites to.
        If no channel is given, the bot stops logging invites for this server."""
        await self.bot.pool.execute(
            f"DELETE FROM invite_logchannel WHERE server_id = {ctx.guild.id}"
        )
        await ctx.message.add_reaction("\U0001f44d")
        if channel:
            await self.bot.pool.execute(
                f"INSERT INTO invite_logchannel (server_id, channel_id) VALUES ($1, $2) ON CONFLICT (server_id) DO UPDATE SET channel_id=excluded.channel_id",
                ctx.guild.id,
                channel.id,
            )
        await self.bot.cogs["events"].update_invites.__call__()

    @commands.hybrid_command()
    @app_commands.describe(server="this must be the server ID")
    async def lurk(self, ctx: commands.Context, server: str = None):
        """Returns a paginator with the server's emojis, if available.
        This should work with servers the bot can see and public servers.
        `server` must be the ID of the server."""
        if server is None:
            server = ctx.guild.id
        else:
            try:
                server = int(server)
            except ValueError:
                return await ctx.send("That's not a valid server ID.", ephemeral=True)
        route = discord.http.Route("GET", "/guilds/{guild_id}/preview", guild_id=server)
        try:
            response = await self.bot.http.request(route)
        except discord.NotFound:
            return await ctx.send(
                "Discord couldn't find that server or the ID is invalid"
            )
        emojis: list[discord.PartialEmoji] = []
        for emoji_data in response.get("emojis"):
            if emoji_data["roles"]:
                continue
            emoji = discord.PartialEmoji.with_state(
                name=emoji_data["name"],
                id=emoji_data["id"],
                animated=emoji_data["animated"],
                state=self.bot._connection,
            )
            emojis.append(emoji)
        icon = f'https://cdn.discordapp.com/icons/{response["id"]}/{response["icon"]}.{"gif" if response["icon"].startswith("a_") else "png"}'
        name = response["name"]
        source = utils.EmojiPageSource(emojis, per_page=1, name=name, icon=icon)
        pages = utils.EmojiPages(source, client=self.bot, ctx=ctx, search=True)
        await pages.start()

    @commands.has_guild_permissions(manage_emojis_and_stickers=True)
    @commands.command(name="sticker")
    async def _sticker(self, ctx: commands.Context):
        """Helper command to create stickers"""
        view = StickerView(ctx.author)
        m = await ctx.send("How do you want to make it?", view=view)
        await view.wait()
        if view.value == 1:
            modal = view.modal
            name = modal.name.value
            description = modal.description.value

            if modal.name.value is None or modal.description.value is None:
                return await m.edit(
                    content="You fucked up submitting the modal or something"
                )

            await m.edit(content="Now send me the sticker in the chat", view=None)

            def check(message: discord.Message):
                return message.author == ctx.author and message.stickers

            try:
                message = await self.bot.wait_for("message", check=check, timeout=120)
            except asyncio.TimeoutError:
                return await m.edit(content="Timed out...")
            sticker: discord.Sticker = message.stickers[0]

            await m.edit(
                content="Last thing, react to this message with a discord default emoji"
            )

            def check(reaction: discord.Reaction, user: discord.User):
                return (
                    (user == ctx.author)
                    and (reaction.message == m)
                    and (isinstance(reaction.emoji, str))
                )

            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add", check=check, timeout=60
                )
            except asyncio.TimeoutError:
                return await m.edit(content="You got timed out")
            try:
                new_sticker = await ctx.guild.create_sticker(
                    name=name,
                    description=description,
                    emoji=str(reaction.emoji),
                    file=(await sticker.to_file()),
                    reason=f"Done by {ctx.author} (ID: {ctx.author.id})",
                )
            except HTTPException as e:
                return await ctx.send(e)
            await message.delete()
            return await ctx.send("Done", stickers=[new_sticker])

        elif view.value == 2:
            modal = view.modal
            name = modal.name.value
            description = modal.description.value

            if modal.name.value is None or modal.description.value is None:
                return await m.edit(
                    content="You fucked up submitting the modal or something"
                )

            await m.edit(content="Send me the image in the chat", view=None)

            def check(message: discord.Message):
                return message.author == ctx.author and message.attachments

            try:
                message = await self.bot.wait_for("message", check=check, timeout=60)
            except asyncio.TimeoutError:
                return await m.edit(content="Timed out...")
            sticker: discord.Sticker = message.attachments[0]

            await m.edit(
                content="Last thing, react to this message with a discord default emoji"
            )

            def check(reaction: discord.Reaction, user: discord.User):
                return (
                    (user == ctx.author)
                    and (reaction.message == m)
                    and (isinstance(reaction.emoji, str))
                )

            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add", check=check, timeout=60
                )
            except asyncio.TimeoutError:
                return await m.edit(content="You got timed out")
            try:
                new_sticker = await ctx.guild.create_sticker(
                    name=name,
                    description=description,
                    emoji=str(reaction.emoji),
                    file=(await sticker.to_file()),
                    reason=f"Done by {ctx.author} (ID: {ctx.author.id})",
                )
            except HTTPException as e:
                return await ctx.send(e)
            await message.delete()
            return await ctx.send("Done", stickers=[new_sticker])
        elif view.value == 3:
            pass  # make them give url through a modal

    @commands.hybrid_command()
    @app_commands.describe(member="The target member")
    async def nicknames(
        self,
        ctx: commands.Context[bot.AndreiBot],
        member: typing.Annotated[discord.Member, utils.CustomMemberTransformer] = None,
    ):
        """Shows member's history of nicknames"""
        if member is None:
            member = await utils.get_member_reference(ctx.message)
        if member is None:
            member = ctx.author
        data = await ctx.bot.pool.fetch(
            "SELECT * FROM nicknames WHERE user_id = $1 AND server_id = $2 ORDER BY datetime DESC",
            member.id,
            ctx.guild.id,
        )
        if not data:
            return await ctx.send(
                f"I don't have any nicknames for {member} in this server"
            )
        pages = utils.SimpleNicknamePages(data, member=member, ctx=ctx)
        await pages.start()

    @commands.hybrid_command()
    @app_commands.describe(user="The target user")
    async def usernames(
        self,
        ctx: commands.Context[bot.AndreiBot],
        user: typing.Annotated[discord.User, utils.CustomUserTransformer] = None,
    ):
        """Shows user's history of usernames"""

        if user is None:
            user = await utils.get_reference(ctx.message)
        if user is None:
            user = ctx.author

        data = await ctx.bot.pool.fetch(
            "SELECT * FROM usernames WHERE user_id = $1 ORDER BY datetime DESC", user.id
        )
        if not data:
            return await ctx.send(f"I don't have any usernames for {user}")
        pages = utils.SimpleUsernamePages(data, user=user, ctx=ctx)
        await pages.start()

    @commands.command()
    async def perms(
        self,
        ctx: commands.Context,
        target: typing.Union[
            utils.MemberConverter, utils.RoleConverter
        ] = commands.Author,
    ):
        """Returns member or role's permissions in the server"""
        embed = discord.Embed(color=discord.Color.orange())
        if isinstance(target, discord.Member):
            perms = get_member_perms(target)
            if not perms:
                raise commands.CommandInvokeError("This member has no special perms")
            embed.set_author(name=target, icon_url=target.display_avatar)
            embed.title = "Permissions for this server"
            embed.description = f"permission value [{target.guild_permissions.value}](https://discordapi.com/permissions.html#{target.guild_permissions.value})\n"
            embed.description += ", ".join(perms)
        elif isinstance(target, discord.Role):
            raise commands.CommandInvokeError("I didnt add it for roles im lazy")
        else:
            raise commands.CommandInvokeError("This should be unreachable code")
        await ctx.send(embed=embed)

    @commands.command(aliases=["info"])
    async def about(self, ctx: commands.Context[bot.AndreiBot]):
        """Returns info about the bot"""
        mb_conv = 1048576
        owner = self.bot.get_user(393033826474917889)
        embed = discord.Embed(
            color=discord.Color.orange(),
            url="https://discord.gg/BFYMAjNv9j",
            title="Server Invite",
        )
        embed.set_author(name=owner, icon_url=owner.display_avatar)
        embed.description = f"Add me with this [URL]({discord.utils.oauth_url(self.bot.user.id, permissions=discord.Permissions.all())})"
        ram = psutil.virtual_memory().total / mb_conv
        used = psutil.virtual_memory().used / mb_conv
        embed.add_field(
            name="System info",
            value=f"RAM `{int(used)}/{int(ram)} MB`\nCPU {psutil.cpu_percent()}%",
        )
        embed.add_field(
            name="Bot RAM usage",
            value=f"`{psutil.Process(os.getpid()).memory_info().rss/mb_conv:.2f} MB`",
        )
        embed.add_field(
            name="Bot started", value=discord.utils.format_dt(self.bot.launch_time, "R")
        )

        embed.add_field(name="Users", value=len(self.bot.users))
        embed.add_field(
            name="Members",
            value=sum(
                [guild.member_count for guild in self.bot.guilds if guild.member_count]
            ),
        )
        embed.add_field(name="Servers", value=len(self.bot.guilds))
        embed.add_field(name="Messages", value=len(self.bot._connection._messages))
        owners = [
            self.bot.get_user(uid).mention
            for uid in self.bot.owner_ids
            if self.bot.get_user(uid)
        ]
        embed.add_field(name="Owners", value=" ".join(owners))
        embed.set_footer(
            text=f"running on python {sys.version}\nmade with discord.py v{pkg_resources.get_distribution('discord.py').version}",
            icon_url="https://cdn.discordapp.com/icons/336642139381301249/3aa641b21acded468308a37eef43d7b3.png",
        )

        await ctx.send(embed=embed)

    @commands.is_owner()
    @commands.command()
    async def reload(self, ctx: commands.Context[bot.AndreiBot]):
        """Reloads all cogs locally"""
        importlib.reload(utils)
        cogs = [cog for cog in ctx.bot.cogs.keys()]
        for cog in cogs:
            if cog in ("Jishaku"):
                continue
            await ctx.bot.unload_extension(f"cogs.{cog.lower()}")
        reloaded = []
        for file in pathlib.Path("cogs").glob("**/[!_]*.py"):
            ext = ".".join(file.parts).removesuffix(".py")
            await ctx.bot.load_extension(ext)
            reloaded.append(ext)
        await ctx.send(f"Reloaded {', '.join(reloaded)}", mention_author=False)


async def setup(bot: bot.AndreiBot) -> None:
    await bot.add_cog(Utility(bot))
