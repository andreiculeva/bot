from __future__ import annotations
import inspect
import itertools
import os
import re
import discord
from discord.ext import commands, menus
from typing import Any, Optional, Dict, List
import aiohttp
import datetime
import asyncio
import contextlib
import random
import io
import humanfriendly
import pytube
import typing
import matplotlib
from matplotlib import pyplot as plt
import async_timeout
import spotipy
import lavalink
from base64 import b64encode
import json
import asyncpg

if typing.TYPE_CHECKING:
    import bot

invis_character = "\U0000200e"
url_rx = re.compile(r"https?://(?:www\.)?.+")
spotify_rx = re.compile(r"spotify.com/(track|playlist)/[a-zA-Z0-9]+")
youtube_rx = re.compile(r"^(https?\:\/\/)?((www\.)?youtube\.com|youtu\.be)\/.+$")
reddit_rx = re.compile(
    r"^http(?:s)?://(?:www\.)?(?:[\w-]+?\.)?reddit.com(/r/|/user/)?(?(1)([\w:]{2,21}))(/comments/)?(?(3)(\w{5,6})(?:/[\w%\\\\-]+)?)?(?(4)/(\w{7}))?/?(\?)?(?(6)(\S+))?(\#)?(?(8)(\S+))?$"
)
twitter_rx = re.compile(
    r"/(?:http:\/\/)?(?:www\.)?twitter|x\.com\/(?:(?:\w)*#!\/)?(?:pages\/)?(?:[\w\-]*\/)*([\w\-]*)/"
)


sp = spotipy.Spotify(
    auth_manager=spotipy.SpotifyClientCredentials(
        client_id="3d04ac62e72a4d7488dbadc924e7126c",
        client_secret="5878ccdee38343918dbdc0da64109e80",
    ),
)

gender_emoji = {"male": "\U00002642", "female": "\U00002640"}



async def make_activity(pool:asyncpg.Pool) -> tuple[discord.Activity, discord.Status]:
    """Returns activity given the database pool"""
    _type = await pool.fetchval(
        "SELECT value FROM internal_config WHERE key = 'status_type'"
    )
    default_status = await pool.fetchval(
        "SELECT value FROM internal_config WHERE key = 'default_status'"
    )
    description = await pool.fetchval(
        "SELECT value FROM internal_config WHERE key = 'status_description'"
    )
    activity = discord.Activity(
        name=description, type=discord.enums.try_enum(discord.ActivityType, int(_type))
    )
    status = discord.enums.try_enum(discord.Status, default_status)
    return activity, status


def url_button(user: discord.User, row: int = None) -> discord.Button:
    return discord.ui.Button(
        label=str(user), url=f"discord://-/users/{user.id}", row=row
    )


profile_emojis = {
    "staff": "<:staff:1005765265390321744>",
    "partner": "<:partner:1005769774896250921>",
    "hypesquad": "<:hypesquadevents:1005767033478205470>",
    "bug_hunter": "<:bughunter:1005767036481318953>",
    "bug_hunter_level_2": "<:bughunter:1005767036481318953>",
    "hypesquad_bravery": "<:bravery:1005767579488501830>",
    "hypesquad_brilliance": "<:brilliance:1005767034975563796>",
    "hypesquad_balance": "<:balance:1005767751526268968>",
    "early_supporter": "<:earlynitro:1005767039660609546>",
    "verified_bot_developer": "<:botdev:1005767038016426014>",
    "discord_certified_moderator": "<:mod:1005765490641223710>",
    "nitro": "<:nitro:1005767041338327040>",
    "bot_http_interactions": "<:slash:1005767345010122753>",
}


activity_emojis = {
    "online": "<:online:1002554648634347640>",
    "offline": "<:offline:1002554608201257060>",
    "dnd": "<:dnd:1002554551959818291>",
    "idle": "<:idle:1002554573896028382>",
}


rx = re.compile(r"([0-9]{15,20})$")


def get_str_time(seconds: int) -> str:
    if seconds == 0:
        return ""
    delta = datetime.timedelta(seconds=seconds)
    return humanfriendly.format_timespan(delta, max_units=2)


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
    )
    clean_perms: List[str] = []
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


class RoboPages(discord.ui.View):
    def __init__(
        self,
        source: menus.PageSource,
        *,
        ctx: commands.Context,
        check_embeds: bool = True,
        compact: bool = False,
    ):
        super().__init__()
        self.source: menus.PageSource = source
        self.check_embeds: bool = check_embeds
        self.ctx: commands.Context = ctx
        self.current_page: int = 0
        self.compact: bool = compact
        self.input_lock = asyncio.Lock()
        self.clear_items()
        self.fill_items()
        self.timeout = 600
        self.interaction: discord.Interaction | None = None
        self.embed = discord.Embed(color=discord.Color.orange())

    def fill_items(self) -> None:
        if not self.compact:
            self.numbered_page.row = 1
            self.stop_pages.row = 1

        if self.source.is_paginating():
            max_pages = self.source.get_max_pages()
            use_last_and_first = max_pages is not None and max_pages >= 2
            if use_last_and_first:
                self.add_item(self.go_to_first_page)  # type: ignore
            self.add_item(self.go_to_previous_page)  # type: ignore
            if not self.compact:
                self.add_item(self.go_to_current_page)  # type: ignore
            self.add_item(self.go_to_next_page)  # type: ignore
            if use_last_and_first:
                self.add_item(self.go_to_last_page)  # type: ignore
            if not self.compact:
                self.add_item(self.numbered_page)  # type: ignore
            self.add_item(self.stop_pages)  # type: ignore

    async def _get_kwargs_from_page(self, page: int) -> Dict[str, Any]:
        value = await discord.utils.maybe_coroutine(self.source.format_page, self, page)
        if isinstance(value, dict):
            return value
        elif isinstance(value, str):
            return {"content": value, "embed": None}
        elif isinstance(value, discord.Embed):
            return {"embed": value, "content": None}
        else:
            return {}

    async def show_page(
        self, interaction: discord.Interaction, page_number: int
    ) -> None:
        page = await self.source.get_page(page_number)
        self.current_page = page_number
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(page_number)
        if kwargs:
            if interaction.response.is_done():
                await self.interaction.edit_original_response(**kwargs, view=self)
            else:
                await interaction.response.edit_message(**kwargs, view=self)

    def _update_labels(self, page_number: int) -> None:
        self.go_to_first_page.disabled = page_number == 0
        if self.compact:
            max_pages = self.source.get_max_pages()
            self.go_to_last_page.disabled = (
                max_pages is None or (page_number + 1) >= max_pages
            )
            self.go_to_next_page.disabled = (
                max_pages is not None and (page_number + 1) >= max_pages
            )
            self.go_to_previous_page.disabled = page_number == 0
            return

        self.go_to_current_page.label = str(page_number + 1)
        self.go_to_previous_page.label = str(page_number)
        self.go_to_next_page.label = str(page_number + 2)
        self.go_to_next_page.disabled = False
        self.go_to_previous_page.disabled = False
        self.go_to_first_page.disabled = False

        max_pages = self.source.get_max_pages()
        if max_pages is not None:
            self.go_to_last_page.disabled = (page_number + 1) >= max_pages
            if (page_number + 1) >= max_pages:
                self.go_to_next_page.disabled = True
                self.go_to_next_page.label = "…"
            if page_number == 0:
                self.go_to_previous_page.disabled = True
                self.go_to_previous_page.label = "…"

    async def show_checked_page(
        self, interaction: discord.Interaction, page_number: int
    ) -> None:
        max_pages = self.source.get_max_pages()
        try:
            if max_pages is None:
                # If it doesn't give maximum pages, it cannot be checked
                await self.show_page(interaction, page_number)
            elif max_pages > page_number >= 0:
                await self.show_page(interaction, page_number)
        except IndexError:
            # An error happened that can be handled, so ignore it.
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        self.interaction = interaction
        if interaction.user == self.ctx.author:
            return True
        elif interaction.user == self.ctx.guild.owner:
            return True
        elif interaction.user.guild_permissions.administrator:
            return True
        elif interaction.user.id in interaction.client.owner_ids:
            return True
        else:
            return await interaction.response.send_message(
                "This button isn't for you", ephemeral=True
            )

    async def on_timeout(self) -> None:
        await self.interaction.edit_original_response(view=None)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(
                "An unknown error occurred, sorry", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "An unknown error occurred, sorry", ephemeral=True
            )

    async def start(self) -> None:
        if (
            self.check_embeds
            and not self.ctx.channel.permissions_for(self.ctx.me).embed_links
        ):
            await self.ctx.send(
                "Bot does not have embed links permission in this channel.",
                ephemeral=True,
            )
            return

        await self.source._prepare_once()  # type:ignore
        page = await self.source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(0)
        await self.ctx.send(**kwargs, view=self, ephemeral=True)

    @discord.ui.button(label="≪", style=discord.ButtonStyle.grey)
    async def go_to_first_page(self, interaction: discord.Interaction, _):
        """go to the first page"""
        await self.show_page(interaction, 0)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.blurple)
    async def go_to_previous_page(self, interaction: discord.Interaction, _):
        """go to the previous page"""
        await self.show_checked_page(interaction, self.current_page - 1)

    @discord.ui.button(label="Current", style=discord.ButtonStyle.grey, disabled=True)
    async def go_to_current_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        pass

    @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple)
    async def go_to_next_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """go to the next page"""
        await self.show_checked_page(interaction, self.current_page + 1)

    @discord.ui.button(label="≫", style=discord.ButtonStyle.grey)
    async def go_to_last_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """go to the last page"""
        # The call here is safe because it's guarded by skip_if
        await self.show_page(interaction, self.source.get_max_pages() - 1)

    @discord.ui.button(label="Skip to page...", style=discord.ButtonStyle.grey)
    async def numbered_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """lets you type a page number to go to"""
        modal = PageModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        page = modal.page.value
        if page is None:
            return await interaction.response.defer(ephemeral=True)
        page = int(modal.page.value) - 1
        await self.show_checked_page(interaction, page)

    @discord.ui.button(label="Quit", style=discord.ButtonStyle.red)
    async def stop_pages(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """stops the pagination session."""
        await interaction.response.edit_message(view=None)
        self.stop()


class UsernamesButton(discord.ui.Button):
    def __init__(self, *, user: discord.User, row: int):
        super().__init__(label="usernames")
        self.user = user
        self.row = row

    async def callback(self, interaction: discord.Interaction) -> Any:
        data = await interaction.client.pool.fetch(
            "SELECT * FROM usernames WHERE user_id = $1 ORDER BY datetime DESC",
            self.user.id,
        )
        if not data:
            return await interaction.response.send_message(
                f"I don't have any usernames for {self.user}", ephemeral=True
            )
        pages = SimpleInteractionUsernamePages(
            data, user=self.user, interaction=interaction, hidden=True
        )
        await pages.start()


class NicknamesButton(discord.ui.Button):
    def __init__(self, *, member: discord.Member, row: int):
        super().__init__(label="nicknames")
        self.member = member
        self.row = row

    async def callback(self, interaction: discord.Interaction) -> Any:
        data = await interaction.client.pool.fetch(
            f"SELECT * FROM nicknames WHERE user_id = $1 AND server_id = {interaction.guild.id} ORDER BY datetime DESC",
            self.member.id,
        )
        if not data:
            return await interaction.response.send_message(
                f"I don't have any nicknames for {self.member} in this server",
                ephemeral=True,
            )
        pages = SimpleInteractionNicknamePages(
            data, member=self.member, interaction=interaction, hidden=True
        )
        await pages.start()


class PermsButton(discord.ui.Button):
    def __init__(self, *, member: discord.Member, row: int):
        super().__init__(label="perms", emoji="<a:ds:839782193076371467>")
        self.member = member
        self.row = row

    async def callback(self, interaction: discord.Interaction) -> Any:
        embed = discord.Embed(color=discord.Color.orange(), title="Perms")
        embed.set_author(name=self.member, icon_url=self.member.display_avatar)
        embed.set_footer(text=f"ID: {self.member.id}")
        perms = get_member_perms(self.member)
        embed.description = f"Permission value [{self.member.guild_permissions.value}](https://discordapi.com/permissions.html#{self.member.guild_permissions.value})\n"
        embed.description += ", ".join(perms)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class RolesButton(discord.ui.Button):
    def __init__(self, *, member: discord.Member, row: int):
        super().__init__(label="roles", emoji="<a:rainbowarrow:767448691367215114>")
        self.member = member
        self.row = row

    async def callback(self, interaction: discord.Interaction) -> Any:
        embed = discord.Embed(color=discord.Color.orange(), title="Roles")
        embed.set_author(name=self.member, icon_url=self.member.display_avatar)
        embed.set_footer(text=f"ID: {self.member.id}")

        embed.description = f", ".join(
            [role.mention for role in self.member.roles if (not role.is_default())]
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)



class HelpMenu(RoboPages):
    def __init__(self, source: menus.PageSource, ctx: commands.Context):
        super().__init__(source, ctx=ctx, compact=True)

    def add_categories(
        self, commands: Dict[commands.Cog, List[commands.Command]]
    ) -> None:
        self.clear_items()
        self.add_item(HelpSelectMenu(commands, self.ctx.bot))
        self.fill_items()

    async def rebind(
        self, source: menus.PageSource, interaction: discord.Interaction
    ) -> None:
        self.source = source
        self.current_page = 0

        await self.source._prepare_once()
        page = await self.source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(0)
        await interaction.response.edit_message(**kwargs, view=self)


class FrontPageSource(menus.PageSource):
    def is_paginating(self) -> bool:
        # This forces the buttons to appear even in the front page
        return True

    def get_max_pages(self) -> typing.Optional[int]:
        # There's only one actual page in the front page
        # However we need at least 2 to show all the buttons
        return 2

    async def get_page(self, page_number: int) -> Any:
        # The front page is a dummy
        self.index = page_number
        return self

    def format_page(self, menu: HelpMenu, page) -> discord.Embed:
        embed = discord.Embed(title="Bot Help", colour=discord.Color.orange())
        embed.description = inspect.cleandoc(
            f"""
            Hello! Welcome to the help page.
            Use "{menu.ctx.clean_prefix}help command" for more info on a command.
            Use "{menu.ctx.clean_prefix}help category" for more info on a category.
            Use the dropdown menu below to select a category.
            You can join the [testing server](https://discord.gg/W9KHWZkHA8).
        """
        )

        entries = (
            ("<argument>", "This means the argument is __**required**__."),
            ("[argument]", "This means the argument is __**optional**__."),
            ("[A|B]", "This means that it can be __**either A or B**__."),
            ("[argument...]", "This means you can have multiple arguments.\n"),
        )

        for name, value in entries:
            embed.add_field(name=name, value=value, inline=False)

        return embed


class HelpSelectMenu(discord.ui.Select["HelpMenu"]):
    def __init__(
        self,
        commands: Dict[commands.Cog, List[commands.Command]],
        bot: commands.AutoShardedBot,
    ):
        super().__init__(
            placeholder="Select a category...",
            min_values=1,
            max_values=1,
            row=0,
        )
        self.commands = commands
        self.bot = bot
        self.__fill_options()

    def __fill_options(self) -> None:
        self.add_option(
            label="Index",
            emoji="\N{WAVING HAND SIGN}",
            value="__index",
            description="The help page showing how to use the bot.",
        )
        for cog, commands in self.commands.items():
            if not commands:
                continue
            description = cog.description.split("\n", 1)[0] or None
            emoji = getattr(cog, "display_emoji", None)
            self.add_option(
                label=cog.qualified_name,
                value=cog.qualified_name,
                description=description,
                emoji=emoji,
            )

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        value = self.values[0]
        if value == "__index":
            await self.view.rebind(FrontPageSource(), interaction)
        else:
            cog = self.bot.get_cog(value)
            if cog is None:
                await interaction.response.send_message(
                    "Somehow this category does not exist?", ephemeral=True
                )
                return

            commands = self.commands[cog]
            if not commands:
                await interaction.response.send_message(
                    "This category has no commands for you", ephemeral=True
                )
                return

            source = GroupHelpPageSource(
                cog, commands, prefix=self.view.ctx.clean_prefix
            )
            await self.view.rebind(source, interaction)


class GroupHelpPageSource(menus.ListPageSource):
    def __init__(
        self,
        group: typing.Union[commands.Group, commands.Cog],
        commands: List[commands.Command],
        *,
        prefix: str,
    ):
        super().__init__(entries=commands, per_page=6)
        self.group = group
        self.prefix = prefix
        self.title = f"{self.group.qualified_name} Commands"
        self.description = self.group.description

    async def format_page(self, menu, commands):
        embed = discord.Embed(
            title=self.title,
            description=self.description,
            colour=discord.Colour.orange(),
        )

        for command in commands:
            signature = f"{command.qualified_name} {command.signature}"
            embed.add_field(
                name=signature,
                value=command.short_doc or "No help given...",
                inline=False,
            )

        maximum = self.get_max_pages()
        if maximum > 1:
            embed.set_author(
                name=f"Page {menu.current_page + 1}/{maximum} ({len(self.entries)} commands)"
            )

        embed.set_footer(
            text=f'Use "{self.prefix}help command" for more info on a command.'
        )
        return embed


class PaginatedHelpCommand(commands.HelpCommand):
    def __init__(self):
        super().__init__(
            command_attrs={
                "cooldown": commands.CooldownMapping.from_cooldown(
                    1, 3.0, commands.BucketType.member
                ),
                "help": "Shows help about the bot, a command, or a category",
            }
        )

    async def on_help_command_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            # Ignore missing permission errors
            if (
                isinstance(error.original, discord.HTTPException)
                and error.original.code == 50013
            ):
                return

            await ctx.send(error.original)

    def get_command_signature(self, command):
        parent = command.full_parent_name
        if len(command.aliases) > 0:
            aliases = "|".join(command.aliases)
            fmt = f"[{command.name}|{aliases}]"
            if parent:
                fmt = f"{parent} {fmt}"
            alias = fmt
        else:
            alias = command.name if not parent else f"{parent} {command.name}"
        return f"{alias} {command.signature}"

    async def send_bot_help(self, mapping):
        bot = self.context.bot

        def key(command) -> str:
            cog = command.cog
            return cog.qualified_name if cog else "\U0010ffff"

        entries: List[commands.Command] = await self.filter_commands(
            bot.commands, sort=True, key=key
        )

        all_commands: Dict[commands.Cog, List[commands.Command]] = {}
        for name, children in itertools.groupby(entries, key=key):
            if name == "\U0010ffff":
                continue

            cog = bot.get_cog(name)
            all_commands[cog] = sorted(children, key=lambda c: c.qualified_name)

        menu = HelpMenu(FrontPageSource(), ctx=self.context)
        menu.add_categories(all_commands)
        await menu.start()

    async def send_cog_help(self, cog):
        entries = await self.filter_commands(cog.get_commands(), sort=True)
        menu = HelpMenu(
            GroupHelpPageSource(cog, entries, prefix=self.context.clean_prefix),
            ctx=self.context,
        )
        await menu.start()

    def common_command_formatting(self, embed_like, command):
        embed_like.title = self.get_command_signature(command)
        if command.description:
            embed_like.description = f"{command.description}\n\n{command.help}"
        else:
            embed_like.description = command.help or "No help found..."

    async def send_command_help(self, command):
        # No pagination necessary for a single command.
        embed = discord.Embed(colour=discord.Colour.orange())
        self.common_command_formatting(embed, command)
        await self.context.send(embed=embed)

    async def send_group_help(self, group):
        subcommands = group.commands
        if len(subcommands) == 0:
            return await self.send_command_help(group)

        entries = await self.filter_commands(subcommands, sort=True)
        if len(entries) == 0:
            return await self.send_command_help(group)

        source = GroupHelpPageSource(group, entries, prefix=self.context.clean_prefix)
        self.common_command_formatting(source, group)
        menu = HelpMenu(source, ctx=self.context)
        await menu.start()


class AvatarConfirmationView(discord.ui.View):
    def __init__(self, *, timeout: Optional[float] = 180):
        super().__init__(timeout=600)
        self.value = False
        self.message: discord.Message = None

    @discord.ui.button(label="yes", style=discord.ButtonStyle.green)
    async def yes(self, interaction: discord.Interaction, _):
        await interaction.response.defer()
        self.value = True
        self.stop()

    @discord.ui.button(label="no", style=discord.ButtonStyle.red)
    async def no(self, interaction: discord.Interaction, _):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.value = False
        self.stop()


class PageModal(discord.ui.Modal, title="Select a page"):
    page = discord.ui.TextInput(
        label="page", style=discord.TextStyle.short, required=True
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not self.page.value.isdigit():
            await interaction.response.send_message(
                f"{self.page.value} is not a valid number", ephemeral=True
            )
            self.page.value = None
            self.stop()

        await interaction.response.defer()
        self.stop()


DONE = [
    "<:done:912190157942308884>",
    "<:done:912190217102970941>",
    "<a:done:912190284698361876>",
    "<a:done:912190377757376532>",
    "<:done:912190445289877504>",
    "<a:done:912190496791728148>",
    "<a:done:912190546192265276>",
    "<a:done:912190649493749811>",
    "<:done:912190753084694558>",
    "<:done:912190821321814046>",
    "<a:done:912190898241167370>",
    "<a:done:912190952200871957>",
    "<a:done:912191063589027880>",
    "<a:done:912191153326145586>",
    "<:done:912191209919897700>",
    "<:done:912191260356407356>",
    "<a:done:912191386575577119>",
    "<:done:912191480351825920>",
    "<:done:912191682534047825>",
    "<a:done:912192596305129522>",
    "<a:done:912192718212583464>",
]


class YoutubeDropdown(discord.ui.View):
    def __init__(self, ctx: commands.Context):
        super().__init__()
        self.ctx = ctx
        self.message: discord.Message = None  # type: ignore

    @discord.ui.select(
        placeholder="Select an activity type...",
        options=[
            discord.SelectOption(label="Cancel", value="cancel", emoji="❌"),
            discord.SelectOption(
                label="Youtube", value="youtube", emoji="<:youtube:898052487989309460>"
            ),
            discord.SelectOption(
                label="Poker", value="poker", emoji="<:poker_cards:917645571274195004>"
            ),
            discord.SelectOption(
                label="Betrayal",
                value="betrayal",
                emoji="<:betrayal:917647390717141072>",
            ),
            discord.SelectOption(label="Fishing", value="fishing", emoji="🎣"),
            discord.SelectOption(
                label="Chess", value="chess", emoji="\U0000265f\U0000fe0f"
            ),
            discord.SelectOption(
                label="Letter Tile",
                value="letter-tile",
                emoji="<:letterTile:917647925927084032>",
            ),
            discord.SelectOption(
                label="Word Snacks",
                value="word-snack",
                emoji="<:wordSnacks:917648019342655488>",
            ),
            discord.SelectOption(
                label="Sketch Heads",
                value="sketch-heads",
                emoji="<:doodle:917648115656437810>",
            ),
            discord.SelectOption(label="Spellcast", value="spellcast", emoji="📜"),
            discord.SelectOption(
                label="Awkword", value="awkword", emoji="<a:typing:895397923687399517>"
            ),
            discord.SelectOption(label="Checkers", value="checkers", emoji="🏁"),
            discord.SelectOption(label="Cancel", value="cancel2", emoji="❌"),
        ],
    )
    async def activity_select(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        member = interaction.user
        if not member.voice:
            await interaction.response.edit_message(
                embed=discord.Embed(
                    color=discord.Color.red(),
                    description="You are not connected to a voice channel",
                ),
                view=None,
            )
            return self.stop()
        if "cancel" in select.values[0]:
            self.stop()
            with contextlib.suppress(discord.HTTPException):
                await interaction.message.delete()
                await self.ctx.message.add_reaction(random.choice(DONE))
            return
        try:
            link = await create_link(
                self.ctx.bot, member.voice.channel, select.values[0]
            )
        except Exception as e:
            self.stop()
            self.ctx.bot.dispatch("command_error", self.ctx, e)
            with contextlib.suppress(discord.HTTPException):
                await self.message.delete()
            return
        em = discord.Embed(
            color=discord.Color.orange(), title=select.values[0].capitalize()
        )
        em.description = f"Click the link to start your activity\n<{link}>"
        em.set_footer(text="activities don't work on mobile")

        await interaction.response.edit_message(content=None, view=None, embed=em)
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.ctx.author:
            return True
        elif interaction.user == self.ctx.guild.owner:
            return True
        elif interaction.user.guild_permissions.administrator:
            return True
        elif interaction.user.id in interaction.client.owner_ids:
            return True
        else:
            return await interaction.response.send_message(
                "This button isn't for you", ephemeral=True
            )

    async def start(self):
        self.message = await self.ctx.send(view=self, mention_author=False)

    async def on_timeout(self) -> None:
        with contextlib.suppress(discord.HTTPException):
            await self.message.edit(view=None)
            await self.ctx.message.add_reaction(random.choice(DONE))


async def create_link(bot: bot.AndreiBot, vc: discord.VoiceChannel, option: str) -> str:

    if not vc.permissions_for(vc.guild.me).create_instant_invite:
        raise commands.BotMissingPermissions(["CREATE_INSTANT_INVITE"])

    data = {
        "max_age": 0,
        "max_uses": 0,
        "target_application_id": event_types.get(option),
        "target_type": 2,
        "temporary": False,
        "validate": None,
    }
    session: aiohttp.ClientSession = bot.session

    async with session.post(
        f"https://discord.com/api/v8/channels/{vc.id}/invites",
        json=data,
        headers={
            "Authorization": f"Bot {bot.http.token}",
            "Content-Type": "application/json",
        },
    ) as resp:
        resp_code = resp.status
        result = await resp.json()

    if resp_code == 429:
        raise commands.BadArgument(
            "You are being rate-limited."
            f'\nTry again in {result.get("X-RateLimit-Reset-After")}s'
        )
    elif resp_code == 401:
        raise commands.BadArgument("Unauthorized")
    elif result["code"] == 10003 or (
        result["code"] == 50035 and "channel_id" in result["errors"]
    ):
        raise commands.BadArgument(
            "For some reason, that voice channel is not valid..."
        )
    elif result["code"] == 50013:
        raise commands.BotMissingPermissions(["CREATE_INSTANT_INVITE"])
    elif result["code"] == 130000:
        raise commands.BadArgument(
            "The api is currently overloaded... Try later maybe?"
        )
    return f"https://discord.gg/{result['code']}"


event_types = {
    "youtube": "880218394199220334",
    "poker": "755827207812677713",
    "betrayal": "773336526917861400",
    "fishing": "814288819477020702",
    "chess": "832012774040141894",
    "letter-tile": "879863686565621790",
    "word-snack": "879863976006127627",
    "sketch-heads": "902271654783242291",
    "spellcast": "852509694341283871",
    "awkword": "879863881349087252",
    "checkers": "832013003968348200",
}


class SimpleBirthdayPageSource(menus.ListPageSource):
    async def format_page(self, menu, entries):
        menu.embed.clear_fields()
        for index, entry in enumerate(entries, start=menu.current_page * self.per_page):
            menu.embed.add_field(
                name=entry["date"],
                value=(f"{entry['user']}" + (entry["age"] if entry["age"] else "")),
                inline=False,
            )

        maximum = self.get_max_pages()
        if maximum > 1:
            footer = (
                f"Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)"
            )
            menu.embed.set_footer(text=footer)

        return menu.embed


class SimpleBirthdayPages(RoboPages):
    """A simple pagination session reminiscent of the old Pages interface.
    Basically an embed with some normal formatting.
    """

    def __init__(
        self,
        entries,
        *,
        ctx: commands.Context,
        per_page: int = 6,
        title="Coming up birthdays",
    ):
        super().__init__(SimpleBirthdayPageSource(entries, per_page=per_page), ctx=ctx)
        self.embed = discord.Embed(colour=discord.Colour.orange(), title=title)


class EmojiView(discord.ui.View):
    def __init__(self, emoji: discord.PartialEmoji, *, timeout: Optional[float] = 180):
        super().__init__(timeout=600)
        self.emoji = emoji
        self.message: discord.Message = None

    @discord.ui.button(label="send file")
    async def _upload_emoji(self, interaction: discord.Interaction, _):
        await interaction.response.defer(ephemeral=True)
        emoji_file = await self.emoji.to_file()
        await interaction.followup.send(
            content=f"{interaction.user} requested file",
            file=emoji_file,
            ephemeral=True,
        )

    async def on_timeout(self) -> None:
        if self.message:
            await self.message.edit(view=None)


class DeletedView(discord.ui.View):
    def __init__(
        self,
        bot: bot.AndreiBot,
        ctx: commands.Context,
        message_id: int,
        author: discord.User,
        *,
        timeout: typing.Optional[float] = 180,
    ):
        super().__init__(timeout=600)
        self.bot = bot
        self.ctx = ctx
        self.message_id = message_id
        self.author = author
        self.file = self.bot.deleted_files.get(message_id)
        if self.file is None:
            self.remove_item(self._snipefile)
        self.message: discord.Message = None

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.red)
    async def _delete_message(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        if interaction.user == self.author:
            pass
        elif not interaction.channel.permissions_for(interaction.user).manage_messages:
            return await interaction.response.send_message(
                "You need to either be the author of that message or have manage messages permissions in this channel to do that",
                ephemeral=True,
            )
        await self.bot.pool.execute(
            f"DELETE FROM deleted_messages WHERE message_id = {self.message_id}"
        )
        await interaction.response.defer()
        await interaction.delete_original_response()

    @discord.ui.button(label="snipe file")
    async def _snipefile(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user == self.author:
            pass
        elif interaction.channel.permissions_for(interaction.user).manage_messages:
            pass
        elif interaction.user.id in interaction.client.owner_ids:
            pass
        else:
            return await interaction.response.send_message(
                f"You need the `manage messages` permission to snipe files",
                ephemeral=True,
            )
        filetuple = self.bot.deleted_files.get(self.message_id)
        if filetuple is None:
            return await interaction.response.send_message(
                f"I don't have that file saved anymore (I delete them after 1 hour)",
                ephemeral=True,
            )
        await interaction.response.defer()
        try:
            await interaction.followup.send(
                file=discord.File(io.BytesIO(filetuple[0]), filename=filetuple[1]),
                content=f"Requested by {interaction.user}",
            )
        except (discord.HTTPException, discord.Forbidden, ValueError, TypeError):
            await interaction.followup.send(content="I couldn't upload that file")

    async def on_timeout(self) -> None:
        if self.message:
            await self.message.edit(view=None)


class ConfirmationView(discord.ui.View):
    def __init__(self, *, ctx: commands.Context, timeout: Optional[float] = 180):
        super().__init__(timeout=600)
        self.value = None
        self.ctx = ctx
        self.message: discord.Message = None

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.value = True
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.ctx.author:
            return True
        elif interaction.user == self.ctx.guild.owner:
            return True
        elif interaction.user.guild_permissions.administrator:
            return True
        elif interaction.user.id in interaction.client.owner_ids:
            return True
        else:
            return await interaction.response.send_message(
                "This button isn't for you", ephemeral=True
            )

    async def on_timeout(self) -> None:
        if self.message:
            await self.message.edit(view=None)


class TimeConverter(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str):
        """This converter returns the time in seconds"""
        time_regex = re.compile(r"(\d{1,5}(?:[.,]?\d{1,5})?)([smhdw])")
        time_dict = {"h": 3600, "s": 1, "m": 60, "d": 86400, "w": 604800}
        matches = time_regex.findall(argument.lower())
        if not matches:
            raise commands.BadArgument("Invalid time given")
        time = 0
        for v, k in matches:
            try:
                time += time_dict[k] * float(v)
            except KeyError:
                raise commands.BadArgument(
                    "{} is an invalid time-key! h/m/s/d are valid!".format(k)
                )
            except ValueError:
                raise commands.BadArgument("{} is not a number!".format(v))
        return time


class InteractionRoboPages(discord.ui.View):
    def __init__(
        self,
        source: menus.PageSource,
        *,
        interaction: discord.Interaction,
        check_embeds: bool = True,
        compact: bool = False,
        hidden: bool = False,
    ):
        super().__init__()
        self.source: menus.PageSource = source
        self.check_embeds: bool = check_embeds
        self.interaction: discord.Interaction = interaction
        self.message: Optional[discord.Message] = None
        self.current_page: int = 0
        self.compact: bool = compact
        self.clear_items()
        self.fill_items()
        self.timeout = 600
        self.hidden: bool = hidden

    def fill_items(self) -> None:
        if not self.compact:
            self.numbered_page.row = 1
            self.stop_pages.row = 1

        if self.source.is_paginating():
            max_pages = self.source.get_max_pages()
            use_last_and_first = max_pages is not None and max_pages >= 2
            if use_last_and_first:
                self.add_item(self.go_to_first_page)  # type: ignore
            self.add_item(self.go_to_previous_page)  # type: ignore
            if not self.compact:
                self.add_item(self.go_to_current_page)  # type: ignore
            self.add_item(self.go_to_next_page)  # type: ignore
            if use_last_and_first:
                self.add_item(self.go_to_last_page)  # type: ignore
            if not self.compact:
                self.add_item(self.numbered_page)  # type: ignore
            self.add_item(self.stop_pages)  # type: ignore

    async def _get_kwargs_from_page(self, page: int) -> Dict[str, Any]:
        value = await discord.utils.maybe_coroutine(self.source.format_page, self, page)
        if isinstance(value, dict):
            return value
        elif isinstance(value, str):
            return {"content": value, "embed": None}
        elif isinstance(value, discord.Embed):
            return {"embed": value, "content": None}
        else:
            return {}

    async def show_page(
        self, interaction: discord.Interaction, page_number: int
    ) -> None:
        page = await self.source.get_page(page_number)
        self.current_page = page_number
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(page_number)
        if kwargs:
            if interaction.response.is_done():
                await interaction.edit_original_response(**kwargs, view=self)
            else:
                await interaction.response.edit_message(**kwargs, view=self)
        else:
            if interaction.response.is_done():
                await interaction.edit_original_response(view=self)
            else:
                await interaction.response.edit_message(view=self)

    def _update_labels(self, page_number: int) -> None:
        self.go_to_first_page.disabled = page_number == 0
        if self.compact:
            max_pages = self.source.get_max_pages()
            self.go_to_last_page.disabled = (
                max_pages is None or (page_number + 1) >= max_pages
            )
            self.go_to_next_page.disabled = (
                max_pages is not None and (page_number + 1) >= max_pages
            )
            self.go_to_previous_page.disabled = page_number == 0
            return

        self.go_to_current_page.label = str(page_number + 1)
        self.go_to_previous_page.label = str(page_number)
        self.go_to_next_page.label = str(page_number + 2)
        self.go_to_next_page.disabled = False
        self.go_to_previous_page.disabled = False
        self.go_to_first_page.disabled = False

        max_pages = self.source.get_max_pages()
        if max_pages is not None:
            self.go_to_last_page.disabled = (page_number + 1) >= max_pages
            if (page_number + 1) >= max_pages:
                self.go_to_next_page.disabled = True
                self.go_to_next_page.label = "…"
            if page_number == 0:
                self.go_to_previous_page.disabled = True
                self.go_to_previous_page.label = "…"

    async def show_checked_page(
        self, interaction: discord.Interaction, page_number: int
    ) -> None:
        max_pages = self.source.get_max_pages()
        try:
            if max_pages is None:
                # If it doesn't give maximum pages, it cannot be checked
                await self.show_page(interaction, page_number)
            elif max_pages > page_number >= 0:
                await self.show_page(interaction, page_number)
        except IndexError:
            # An error happened that can be handled, so ignore it.
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        self.interaction = interaction
        if interaction.user == self.interaction.user:
            return True
        elif interaction.user == interaction.guild.owner:
            return True
        elif interaction.user.guild_permissions.administrator:
            return True
        elif interaction.user.id in interaction.client.owner_ids:
            return True
        else:
            return await interaction.response.send_message(
                "This button isn't for you", ephemeral=True
            )

    async def on_timeout(self) -> None:
        await self.interaction.edit_original_response(view=None)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(
                "An unknown error occurred, sorry", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "An unknown error occurred, sorry", ephemeral=True
            )

    async def start(self) -> None:
        if (
            self.check_embeds
            and not self.interaction.channel.permissions_for(
                self.interaction.guild.me
            ).embed_links
        ):
            await self.interaction.response.send_message(
                "Bot does not have embed links permission in this channel.",
                ephemeral=True,
            )
            return

        await self.source._prepare_once()
        page = await self.source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(0)
        await self.interaction.response.send_message(
            ephemeral=True, view=self, **kwargs
        )

    @discord.ui.button(label="≪", style=discord.ButtonStyle.grey)
    async def go_to_first_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """go to the first page"""
        await self.show_page(interaction, 0)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.blurple)
    async def go_to_previous_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """go to the previous page"""
        await self.show_checked_page(interaction, self.current_page - 1)

    @discord.ui.button(label="Current", style=discord.ButtonStyle.grey, disabled=True)
    async def go_to_current_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        pass

    @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple)
    async def go_to_next_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """go to the next page"""
        await self.show_checked_page(interaction, self.current_page + 1)

    @discord.ui.button(label="≫", style=discord.ButtonStyle.grey)
    async def go_to_last_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """go to the last page"""
        # The call here is safe because it's guarded by skip_if
        await self.show_page(interaction, self.source.get_max_pages() - 1)

    @discord.ui.button(label="Skip to page...", style=discord.ButtonStyle.grey)
    async def numbered_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """lets you type a page number to go to"""
        modal = PageModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        page = modal.page.value
        if page is None:
            return await interaction.response.defer(ephemeral=True)
        page = int(modal.page.value) - 1
        await self.show_checked_page(interaction, page)

    @discord.ui.button(label="Quit", style=discord.ButtonStyle.red)
    async def stop_pages(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """stops the pagination session."""
        await interaction.response.edit_message(view=None)
        self.stop()


class InteractionDeletedView(discord.ui.View):
    def __init__(
        self,
        bot: bot.AndreiBot,
        interaction: discord.Interaction,
        hidden: bool,
        message_id: int,
        author: discord.User,
        *,
        timeout: typing.Optional[float] = 180,
    ):
        super().__init__(timeout=600)
        self.bot = bot
        self.interaction = interaction
        self.message_id = message_id
        self.hidden = hidden
        self.author = author
        self.file = self.bot.deleted_files.get(message_id)
        if self.file is None:
            self.remove_item(self._snipefile)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.red)
    async def _delete_message(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        if interaction.user == self.author:
            pass
        elif not interaction.channel.permissions_for(interaction.user).manage_messages:
            return await interaction.response.send_message(
                "You need to either be the author of that message or have manage messages permissions in this channel to do that",
                ephemeral=True,
            )
        bot: bot.AndreiBot = interaction.client
        await bot.pool.execute(
            f"DELETE FROM deleted_messages WHERE message_id = {self.message_id}"
        )
        await interaction.response.defer()
        await interaction.delete_original_response()

    @discord.ui.button(label="snipe file")
    async def _snipefile(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user == self.interaction.user:
            pass
        elif interaction.channel.permissions_for(interaction.user).manage_messages:
            pass
        elif interaction.user.id in interaction.client.owner_ids:
            pass
        else:
            return await interaction.response.send_message(
                f"You need the `manage messages` permission to snipe files",
                ephemeral=True,
            )
        filetuple = self.bot.deleted_files.get(self.message_id)
        if filetuple is None:
            return await interaction.response.send_message(
                f"I don't have that file saved anymore (I delete them after 1 hour)",
                ephemeral=True,
            )
        await interaction.response.defer(ephemeral=self.hidden)
        try:
            await interaction.followup.send(
                file=discord.File(io.BytesIO(filetuple[0]), filename=filetuple[1]),
                content=f"Requested by {interaction.user}",
            )
        except (discord.HTTPException, discord.Forbidden, ValueError, TypeError):
            await interaction.followup.send(content="I couldn't upload that file")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        self.interaction = interaction
        return True

    async def on_timeout(self) -> None:
        await self.interaction.edit_original_response(view=None)


class EmojiSearchModal(discord.ui.Modal, title="Search emojis"):
    name = discord.ui.TextInput(label="name")

    def __init__(
        self, *, title: str = "emoji search", emojis: list[discord.PartialEmoji]
    ) -> None:
        self.emojis = emojis
        super().__init__(title=title)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        entries = []
        for emoji in self.emojis:
            if self.name.value.lower() in emoji.name.lower():
                entries.append(emoji)

        if not entries:
            return await interaction.response.send_message(
                f"No results for {self.name.value}", ephemeral=True
            )
        await interaction.response.defer(ephemeral=True)

        source = EmojiPageSource(entries, per_page=1)
        pages = EmojiPages(
            source,
            client=interaction.client,
            ctx=(await interaction.client.get_context(interaction)),
            search=False,
        )
        pages.embed.set_author(
            name=interaction.user, icon_url=interaction.user.display_avatar
        )
        pages.embed.add_field(
            name=f"{len(entries)} emojis matching", value=f"{self.name.value}"
        )
        await pages.start()


class EmojiPageSource(menus.ListPageSource):
    def __init__(self, entries, *, per_page, icon=None, name=None):
        super().__init__(entries, per_page=per_page)
        self.entries = entries
        self.icon = icon
        self.name = name

    async def format_page(self, menu: menus.Menu, entry: discord.PartialEmoji):
        if self.name:
            menu.embed.set_author(name=self.name, icon_url=self.icon)
        maximum = self.get_max_pages()
        if maximum > 1:
            footer = (
                f"Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)"
            )
            menu.embed.set_footer(text=footer)
        menu.embed.set_image(url=entry.url)
        emoji_str = f"<{'a' if entry.animated else ''}:{entry.name}:{entry.id}>"
        menu.embed.description = f"`{emoji_str}`\n[URL]({entry.url})"
        return menu.embed


class EmojiPages(RoboPages):
    def __init__(
        self,
        source: menus.PageSource,
        *,
        search: bool = True,
        client: bot.AndreiBot,
        check_embeds: bool = True,
        compact: bool = False,
        ctx: commands.Context,
    ):
        self.search = search
        super().__init__(source, ctx=ctx, check_embeds=check_embeds, compact=compact)
        self.client = client
        self.author = ctx.author
        self.message: Optional[discord.Message] = None
        self.current_page: int = 0
        self.input_lock = asyncio.Lock()
        self.clear_items()
        self.fill_items()
        self.timeout = 600
        self.embed = discord.Embed(color=discord.Color.orange())

    def fill_items(self) -> None:
        super().fill_items()
        if self.search:
            self.add_item(self._search)
        self.add_item(self._steal)
        self.add_item(self.stop_pages)

    @discord.ui.button(label="search")
    async def _search(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.send_modal(
            EmojiSearchModal(title="Search for emojis", emojis=self.source.entries)
        )

    @discord.ui.button(label="steal")
    async def _steal(self, interaction: discord.Interaction, button: discord.Button):
        if not interaction.user.guild_permissions.manage_emojis:
            return await interaction.response.send_message(
                "You don't have the permissions to do that!", ephemeral=True
            )
        await interaction.response.defer(ephemeral=True)
        emoji: discord.PartialEmoji = self.source.entries[self.current_page]
        bytes = await emoji.read()
        try:
            new_emoji = await interaction.guild.create_custom_emoji(
                name=emoji.name,
                image=bytes,
                reason=f"Action done by {interaction.user} (ID: {interaction.user.id})",
            )
            em = discord.Embed(
                color=discord.Color.green(),
                description=f"done {new_emoji}\nname: {new_emoji.name}\nID: {new_emoji.id}\nanimated: {new_emoji.animated}\n`{new_emoji}`",
            )
            em.set_thumbnail(url=new_emoji.url)
            em.set_author(
                name=interaction.user, icon_url=interaction.user.display_avatar
            )
            await interaction.followup.send(embed=em)
        except discord.HTTPException as e:
            await interaction.followup.send(e, ephemeral=True)


class TikTokVideo:
    def __init__(self, video: io.BytesIO, url: str, download_url: str) -> None:
        self.video = video
        self.url = url
        self.download_url = download_url


class UrbanDictionaryPageSource(menus.ListPageSource):
    BRACKETED = re.compile(r"(\[(.+?)\])")

    def __init__(self, data):
        super().__init__(entries=data, per_page=1)

    def cleanup_definition(self, definition, *, regex=BRACKETED):
        def repl(m):
            word = m.group(2)
            return f'[{word}](http://{word.replace(" ", "-")}.urbanup.com)'

        ret = regex.sub(repl, definition)
        if len(ret) >= 2048:
            return ret[0:2000] + " [...]"
        return ret

    async def format_page(self, menu, entry):
        maximum = self.get_max_pages()
        title = (
            f'{entry["word"]}: {menu.current_page + 1} out of {maximum}'
            if maximum
            else entry["word"]
        )
        embed = discord.Embed(title=title, colour=0xE86222, url=entry["permalink"])
        embed.set_footer(text=f'by {entry["author"]}')
        embed.description = self.cleanup_definition(entry["definition"])

        try:
            up, down = entry["thumbs_up"], entry["thumbs_down"]
        except KeyError:
            pass
        else:
            embed.add_field(
                name="Votes",
                value=f"\N{THUMBS UP SIGN} {up} \N{THUMBS DOWN SIGN} {down}",
                inline=False,
            )

        try:
            date = discord.utils.parse_time(entry["written_on"][0:-1])
        except (ValueError, KeyError):
            pass
        else:
            embed.timestamp = date

        return embed



class RoleSimplePageSource(menus.ListPageSource):
    async def format_page(self, menu: menus.Menu, entries: list[discord.Member]):
        pages = []
        # one emoji per page
        for index, member in enumerate(entries, start=menu.current_page * 1):
            pages.append(f"{member}")

        maximum = self.get_max_pages()
        if maximum > 1:
            footer = f"Page {menu.current_page + 1}/{maximum}"
            if self.role.id == 849833845603696690:
                footer += f" ({len(self.entries)}/{len([m for m in self.role.guild.members if not m.bot])})"
            else:
                footer += f" ({len(self.entries)} entries)"
            menu.embed.set_footer(text=footer)
        menu.embed.description = "\n".join(pages)
        return menu.embed


class EmojiPageSource(menus.ListPageSource):
    def __init__(self, entries, *, per_page, icon=None, name=None):
        super().__init__(entries, per_page=per_page)
        self.entries = entries
        self.icon = icon
        self.name = name

    async def format_page(self, menu: menus.Menu, entry: discord.PartialEmoji):
        if self.name:
            menu.embed.set_author(name=self.name, icon_url=self.icon)
        maximum = self.get_max_pages()
        if maximum > 1:
            footer = (
                f"Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)"
            )
            menu.embed.set_footer(text=footer)
        menu.embed.set_image(url=entry.url)
        emoji_str = f"<{'a' if entry.animated else ''}:{entry.name}:{entry.id}>"
        menu.embed.description = f"`{emoji_str}`\n[URL]({entry.url})"
        return menu.embed


class RolePages(RoboPages):
    """A simple pagination session reminiscent of the old Pages interface.
    Basically an embed with some normal formatting.
    """

    def __init__(
        self, entries, *, ctx: commands.Context, per_page: int = 12, role: discord.Role
    ):
        source = RoleSimplePageSource(entries=entries, per_page=per_page)
        source.role = role
        super().__init__(source, ctx=ctx)
        self.embed = discord.Embed(
            colour=discord.Colour.orange(),
            title=f"Members in {role.name}",
            description=f"{role.mention}\n\n",
        )
        self.emojis: list[discord.PartialEmoji] = entries


class ConfirmationDeleteView(discord.ui.View):
    def __init__(
        self,
        ctx: commands.Context,
        emoji: discord.Emoji,
        *,
        timeout: Optional[float] = 180,
    ):
        super().__init__(timeout=600)
        self.ctx = ctx
        self.emoji = emoji
        self.message: discord.Message = None

    @discord.ui.button(style=discord.ButtonStyle.green, emoji="\U0001f44d")
    async def _delete_emoji_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.emoji.delete(reason=f"Deleted by {self.ctx.author}")
        await interaction.response.edit_message(
            embed=discord.Embed(
                color=discord.Color.orange(), description="Done \U0001f44d"
            ),
            view=None,
        )
        self.stop()

    @discord.ui.button(style=discord.ButtonStyle.red, emoji="\U0001f44e")
    async def _cancel_everything(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.edit_message(
            embed=discord.Embed(
                color=discord.Color.orange(), description="Ok, canceled"
            ),
            view=None,
        )
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.ctx.author:
            return True
        elif interaction.user == self.ctx.guild.owner:
            return True
        elif interaction.user.guild_permissions.administrator:
            return True
        elif interaction.user.id in interaction.client.owner_ids:
            return True
        else:
            return await interaction.response.send_message(
                "This button isn't for you", ephemeral=True
            )

    async def on_timeout(self) -> None:
        if self.message:
            await self.message.edit(view=None)


class SimplePageSource(menus.ListPageSource):
    async def format_page(self, menu, entries):
        pages = []
        for index, entry in enumerate(entries, start=menu.current_page * self.per_page):
            pages.append(f"{index + 1}. {entry}")

        maximum = self.get_max_pages()
        if maximum > 1:
            footer = (
                f"Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)"
            )
            menu.embed.set_footer(text=footer)

        menu.embed.description = "\n".join(pages)
        return menu.embed


class SimplePages(RoboPages):
    """A simple pagination session reminiscent of the old Pages interface.
    Basically an embed with some normal formatting.
    """

    def __init__(
        self,
        entries,
        *,
        ctx: commands.Context,
        per_page: int = 12,
        title=None,
        description=None,
        footer=None,
    ):
        super().__init__(SimplePageSource(entries, per_page=per_page), ctx=ctx)
        self.embed = discord.Embed(colour=discord.Colour.orange(), title=title)
        if description:
            self.embed.add_field(name=description, value="\u200b")
        if footer:
            self.embed.set_footer(text=footer)


class SnipeSimplePageSource(menus.ListPageSource):
    async def format_page(self, menu, entries):
        entry = entries
        content = (
            f"{discord.utils.format_dt(entry['datetime'])}\n{entry['message_content']}"
        )
        maximum = self.get_max_pages()
        if maximum > 1:
            footer = (
                f"Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)"
            )
            menu.embed.set_footer(text=footer)

        menu.embed.clear_fields()
        num = str(menu.current_page + 1)
        if num[-1] == "1":
            num += "st"
        elif num[-1] == "2":
            num += "nd"
        elif num[-1] == "3":
            num += "rd"
        else:
            num += "th"

        menu.embed.add_field(
            name=f"{num} edit",
            value=content
            if (len(content) < 1024)
            else f"{content[:960]}\n\n----REST IS TOO LONG TO DISPLAY----",
        )

        return menu.embed


class SnipeSimplePages(RoboPages):
    """A simple pagination session reminiscent of the old Pages interface.
    Basically an embed with some normal formatting.
    """

    def __init__(
        self, entries, *, ctx: commands.Context, original, author: discord.User
    ):
        super().__init__(SnipeSimplePageSource(entries=entries, per_page=1), ctx=ctx)
        self.embed = discord.Embed(colour=discord.Colour.orange())
        # begins with formatted timestamp + original content
        if author:
            self.embed.set_author(name=author, icon_url=author.display_avatar)
        self.embed.title = "Original"
        self.embed.description = f"{discord.utils.format_dt(original['datetime'])}\n{original['message_content']}\n\n"


def format_description(s: pytube.Stream):
    parts = [f"{s.mime_type}"]
    if s.includes_video_track:
        parts.extend([f'{"with" if s.includes_audio_track else "without"} audio'])
        parts.extend([f"{s.resolution}", f"@{s.fps}fps"])

    else:
        parts.extend([f"{s.abr}", f'audio codec="{s.audio_codec}"'])
    return f"{' '.join(parts)}"


class YouTubeDownloadSelect(discord.ui.View):
    def __init__(
        self,
        *,
        timeout: Optional[float] = 180,
        streams: pytube.StreamQuery,
        ctx: commands.Context,
    ):
        super().__init__(timeout=600)
        self.options = streams
        self.audio: bool = False
        self.all_pts: bool = False
        self.ctx = ctx
        for stream in self.options.filter(progressive=True):
            s = format_description(stream)
            self._select.add_option(
                description=s,
                value=str(stream.itag),
                label=f"{stream.resolution} @{stream.fps}fps",
            )
        self.message: discord.Message = None

    @discord.ui.button(label="all options", style=discord.ButtonStyle.red)
    async def all_options(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        self.all_pts = not self.all_pts
        if self.all_pts:
            button.style = discord.ButtonStyle.green
        else:
            button.style = discord.ButtonStyle.red

        if self.all_pts:
            self._select.options.clear()
            opts = self.options
            if len(opts) > 25:
                opts = opts[:25]
            for stream in opts:
                s = format_description(stream)
                self._select.add_option(
                    description=s, value=str(stream.itag), label=f"{stream.mime_type}"
                )
        elif self.audio:
            self._select.options.clear()
            for stream in self.options.filter(only_audio=True):
                s = format_description(stream)
                self._select.add_option(label=s, value=str(stream.itag))
        else:
            self._select.options.clear()
            for stream in self.options.filter(progressive=True):
                s = format_description(stream)
                self._select.add_option(
                    description=s,
                    value=str(stream.itag),
                    label=f"{stream.resolution} @{stream.fps}fps",
                )

        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="audio only", style=discord.ButtonStyle.red)
    async def _audio_only(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        self.audio = not self.audio
        if self.audio:
            button.style = discord.ButtonStyle.green
        else:
            button.style = discord.ButtonStyle.red

        if self.audio:
            self._select.options.clear()
            for stream in self.options.filter(only_audio=True):
                s = format_description(stream)
                self._select.add_option(label=s, value=str(stream.itag))
            pass
        else:
            self._select.options.clear()
            for stream in self.options.filter(progressive=True):
                s = format_description(stream)
                self._select.add_option(
                    description=s,
                    value=str(stream.itag),
                    label=f"{stream.resolution} @{stream.fps}fps",
                )

        await interaction.response.edit_message(view=self)

    @discord.ui.select()
    async def _select(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        await interaction.response.defer(thinking=True)
        if self.all_pts:
            self._select.options.clear()
            for stream in self.options:

                s = format_description(stream)
                self._select.add_option(
                    description=s, value=str(stream.itag), label=f"{stream.mime_type}"
                )
        elif self.audio:
            self._select.options.clear()
            for stream in self.options.filter(only_audio=True):
                s = format_description(stream)
                self._select.add_option(label=s, value=str(stream.itag))
            pass
        else:
            self._select.options.clear()
            for stream in self.options.filter(progressive=True):
                s = format_description(stream)
                self._select.add_option(
                    description=s,
                    value=str(stream.itag),
                    label=f"{stream.resolution} @{stream.fps}fps",
                )
        video = self.options.get_by_itag(int(select.values[0]))

        _bot: bot.AndreiBot = interaction.client
        em = discord.Embed(
            color=discord.Color.orange(),
            description=f"[click here to download]({video.url})",
        )

        if self.audio:
            em.description += "\nnote: this is a raw audio file, you'll have to change the file extension to `.mp3` or encode it yourself if it doesn't work"
        try:
            async with async_timeout.timeout(300):
                async with _bot.session.get(video.url) as response:
                    video_bytes = await response.read()
                try:
                    await interaction.followup.send(
                        file=discord.File(
                            io.BytesIO(video_bytes), filename=video.default_filename
                        )
                    )
                except discord.HTTPException as e:
                    raise commands.CommandInvokeError("Timed out downloading the file")
                    file_name = (
                        f'{self.ctx.author.id}.{video.default_filename.split(".")[-1]}'
                    )
                    with open(file_name, "wb") as fp:
                        fp.write(video_bytes)
                    os.rename(
                        file_name,
                        f"/home/ubuntu/Desktop/share/Media/{file_name}",
                    )
                    await interaction.followup.send(
                        f"I can't upload the file in this chat\nYou can download it from [here](http://vps-51b50163.vps.ovh.net:5000/{file_name})"
                    )
        except asyncio.TimeoutError:
            return await interaction.followup.send("Timed out downloading the file")

    async def on_timeout(self) -> None:
        if self.message:
            await self.message.edit(view=None)


class InteractionSnipeSimplePageSource(menus.ListPageSource):
    async def format_page(self, menu, entries):
        entry = entries

        content = f"{discord.utils.format_dt(entry[1])}\n{entry[0]}"
        maximum = self.get_max_pages()
        if maximum > 1:
            footer = (
                f"Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)"
            )
            menu.embed.set_footer(text=footer)

        menu.embed.clear_fields()
        num = str(menu.current_page + 1)
        if num[-1] == "1":
            num += "st"
        elif num[-1] == "2":
            num += "nd"
        elif num[-1] == "3":
            num += "rd"
        else:
            num += "th"

        menu.embed.add_field(
            name=f"{num} edit",
            value=content
            if (len(content) < 1024)
            else f"{content[:960]}\n\n----REST IS TOO LONG TO DISPLAY----",
        )

        return menu.embed


class InteractionSnipeSimplePages(InteractionRoboPages):
    """A simple pagination session reminiscent of the old Pages interface.
    Basically an embed with some normal formatting.
    """

    def __init__(
        self,
        entries,
        *,
        interaction: discord.Interaction,
        original,
        author: discord.User,
        hidden: bool = False,
    ):
        super().__init__(
            InteractionSnipeSimplePageSource(entries=entries, per_page=1),
            interaction=interaction,
            hidden=hidden,
        )
        self.embed = discord.Embed(colour=discord.Colour.orange())
        # begins with formatted timestamp + original content
        if author:
            self.embed.set_author(name=author, icon_url=author.display_avatar)
        self.embed.title = "Original"
        self.embed.description = (
            f"{discord.utils.format_dt(original[1])}\n{original[0]}\n\n"
        )



class ChimpButton(discord.ui.Button):
    def __init__(
        self,
        *,
        label: typing.Optional[str] = None,
        style: discord.ButtonStyle = discord.ButtonStyle.gray,
        disabled: bool = False,
        x: int,
        y: int,
    ):
        super().__init__(
            style=discord.ButtonStyle.secondary, label=label, disabled=disabled
        )
        self.x = x
        self.y = y
        self.view: ChimpView
        self.value = 0

    async def end_game(self):
        self.style = discord.ButtonStyle.red
        for button in self.view.children:
            button.disabled = True
            if button.value != 0:
                if button.style == discord.ButtonStyle.green:
                    continue
                button.label = str(button.value)
        self.view.stop()
        self.view.lost = True
        if self.view.previous:
            self.view.message = f"Your record is {self.view.max-1}"
            await self.view.update_record()
        else:
            self.view.message = "You lost"

    async def win_game(self):
        self.style = discord.ButtonStyle.green
        self.view.message = "You completed the game"
        self.view.stop()
        await self.view.update_record()

    async def callback(self, interaction: discord.Interaction):
        self.view.timeout = 60
        self.view.expires = discord.utils.utcnow() + datetime.timedelta(
            seconds=self.view.timeout
        )
        self.disabled = True
        if self.value == 1:
            time_taken = discord.utils.utcnow() - self.view.started
            self.view.previous_time_taken = self.view.time_taken
            self.view.time_taken = time_taken.seconds
            for button in self.view.children:
                button.label = invis_character
        if self.value == self.view.current:  # guess
            self.style = discord.ButtonStyle.green
            self.view.current = self.view.current + 1
            self.label = str(self.value)
            self.view.message = f"You guessed {self.value}/{self.view.max} (You can reply until {discord.utils.format_dt(self.view.expires, 'T')})"
            if self.view.current == self.view.max + 1:
                if self.view.lost:
                    await self.end_game()
                else:
                    self.view.previous = True
                    self.view.max += 1
                    if self.view.max == 26:
                        await self.win_game()
                    else:
                        self.view.initialize_game()
        else:  # wrong button
            await self.end_game()
        await interaction.response.edit_message(
            view=self.view, content=self.view.message
        )


class ChimpView(discord.ui.View):
    def __init__(
        self,
        amount: int,
        author: discord.User,
        bot: bot.AndreiBot,
        *,
        timeout: typing.Optional[float] = 90,
    ):
        super().__init__(timeout=timeout)
        """This creates the game view and prepares the first game with self.max numbers"""
        self.started = discord.utils.utcnow()
        self.time_taken = 0
        self.previous_time_taken = 0
        self.expires = discord.utils.utcnow() + datetime.timedelta(seconds=timeout)
        self.previous = False
        self.board = [[0] * 5] * 5
        self.author = author
        self.current: int = 1
        self.children: list[ChimpButton]
        self.max: int = amount  # how many numbers
        self.button_coordinates = []
        self.embed: discord.Embed = None
        self.lost = False
        self.message = ""
        self.bot = bot
        self.m: discord.Message = None
        for column in range(1, 6):
            for row in range(1, 6):
                button = ChimpButton(
                    x=column,
                    y=row,
                    label=" ",
                    disabled=True,
                    style=discord.ButtonStyle.gray,
                )
                self.add_item(button)
                self.board[row - 1][column - 1] = button
        self.initialize_game()

    async def on_timeout(self) -> None:
        for button in self.children:
            button.disabled = True
        if self.previous:
            await self.m.edit(
                view=self,
                content=f"I don't know wtf you're doing but you're taking too long to reply, your score is {self.max-1}",
            )
            await self.update_record()
        else:
            await self.m.edit(view=self, content="You got timed out")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.author:
            return True
        await interaction.response.send_message(
            f"This game is for {self.author} (ID: {self.author.id})", ephemeral=True
        )

    def initialize_game(self):
        """This edits the board with random coordinates of the buttons and x numbers to guess based on self.max"""
        self.started = discord.utils.utcnow()
        self.timeout = self.max * 60
        self.expires = discord.utils.utcnow() + datetime.timedelta(seconds=self.timeout)
        self.message = f"Memorize the numbers on the grid and tap on the first one to start the game (You can reply until {discord.utils.format_dt(self.expires, 'T')})"
        self.current = 1
        for button in self.children:
            button.label = invis_character
            button.disabled = True
            button.style = discord.ButtonStyle.gray
            button.value = 0
        button_coordinates = []
        for button_number in range(1, self.max + 1):
            new_coordinate = (random.randint(1, 5), random.randint(1, 5), button_number)
            while (new_coordinate[0], new_coordinate[1]) in [
                (x[0], x[1]) for x in button_coordinates
            ]:
                new_coordinate = (
                    random.randint(1, 5),
                    random.randint(1, 5),
                    button_number,
                )
            button_coordinates.append(new_coordinate)
        self.button_coordinates = button_coordinates
        for x, y, number in self.button_coordinates:
            for b in self.children:
                if b.x == x and b.y == y:
                    b.label = str(number)
                    b.value = number
                    b.disabled = False
                    b.style = discord.ButtonStyle.blurple

    async def update_record(self):
        data = await self.bot.pool.fetchrow(
            f"SELECT * FROM chimps WHERE user_id = {self.author.id}"
        )
        if not data:
            await self.bot.pool.execute(
                "INSERT INTO chimps (user_id, score, play_time) VALUES ($1, $2, $3)",
                self.author.id,
                self.max - 1,
                datetime.timedelta(seconds=self.previous_time_taken),
            )
        elif data["score"] < self.max - 1:
            await self.bot.pool.execute(
                f"DELETE FROM chimps WHERE user_id = {self.author.id}"
            )
            await self.bot.pool.execute(
                "INSERT INTO chimps (user_id, score, play_time) VALUES ($1, $2, $3)",
                self.author.id,
                self.max - 1,
                datetime.timedelta(seconds=self.previous_time_taken),
            )
        await self.m.add_reaction("\U0001f3c5")


class MutedPages(RoboPages):
    """A simple pagination session reminiscent of the old Pages interface.
    Basically an embed with some normal formatting.
    """

    def __init__(self, entries, *, ctx: commands.Context, per_page: int = 12):
        source = MutedPageSource(entries=entries, per_page=per_page)
        super().__init__(source, ctx=ctx)
        self.embed = discord.Embed(
            colour=discord.Colour.orange(), title=f"Members muted"
        )


class MutedPageSource(menus.ListPageSource):
    async def format_page(self, menu: menus.Menu, entries: list[discord.Member]):
        pages = []
        for index, member in enumerate(entries, start=menu.current_page * 1):
            pages.append(f"{member} {discord.utils.format_dt(member.timed_out_until)}")

        maximum = self.get_max_pages()
        if maximum > 1:
            footer = (
                f"Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)"
            )
            menu.embed.set_footer(text=footer)
        menu.embed.description = "\n".join(pages)
        return menu.embed


class UserConverter(commands.Converter):
    async def convert(
        self, ctx: commands.Context[bot.AndreiBot], argument: str
    ) -> discord.User:

        match = rx.match(argument) or re.match(r"<@!?([0-9]{15,20})>$", argument)
        result = None
        state = ctx._state

        if match is not None:
            user_id = int(match.group(1))
            result = ctx.bot.get_user(user_id)
            if result is None:
                try:
                    result = await ctx.bot.fetch_user(user_id)
                except discord.HTTPException:
                    raise commands.UserNotFound(argument) from None

            return result  # type: ignore

        arg = argument

        # Remove the '@' character if this is the first character from the argument
        if arg[0] == "@":
            # Remove first character
            arg = arg[1:]

        # check for discriminator if it exists,
        if len(arg) > 5 and arg[-5] == "#":
            discrim = arg[-4:]
            name = arg[:-5]

            def predicate(u):
                return u.name == name and u.discriminator == discrim

            result = discord.utils.find(predicate, state._users.values())
            if result is not None:
                return result

        def predicate(u):
            return u.name.lower() == arg.lower()

        result = discord.utils.find(predicate, state._users.values())
        if result:
            return result

        def predicate(user):
            return str(user).lower().startswith(argument.lower())

        result = discord.utils.find(predicate, state._users.values())
        if result:
            return result

        if result is None:
            raise commands.UserNotFound(argument)

        return result


class MemberConverter(commands.Converter):
    """Converts to a :class:`~discord.Member`.

    All lookups are via the local guild. If in a DM context, then the lookup
    is done by the global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by mention.
    3. Lookup by name#discrim
    4. Lookup by name
    5. Lookup by nickname

    .. versionchanged:: 1.5
         Raise :exc:`.MemberNotFound` instead of generic :exc:`.BadArgument`

    .. versionchanged:: 1.5.1
        This converter now lazily fetches members from the gateway and HTTP APIs,
        optionally caching the result if :attr:`.MemberCacheFlags.joined` is enabled.
    """

    async def query_member_named(
        self, guild: discord.Guild, argument: str
    ) -> Optional[discord.Member]:
        cache = guild._state.member_cache_flags.joined
        if len(argument) > 5 and argument[-5] == "#":
            username, _, discriminator = argument.rpartition("#")
            members = await guild.query_members(username, limit=100, cache=cache)
            return discord.utils.get(
                members, name=username, discriminator=discriminator
            )
        else:
            members = await guild.query_members(argument, limit=100, cache=cache)
            return discord.utils.find(
                lambda m: m.name == argument or m.nick == argument, members
            )

    async def query_member_by_id(
        self, bot: bot.AndreiBot, guild: discord.Guild, user_id: int
    ) -> Optional[discord.Member]:
        ws = bot._get_websocket(shard_id=guild.shard_id)
        cache = guild._state.member_cache_flags.joined
        if ws.is_ratelimited():
            # If we're being rate limited on the WS, then fall back to using the HTTP API
            # So we don't have to wait ~60 seconds for the query to finish
            try:
                member = await guild.fetch_member(user_id)
            except discord.HTTPException:
                return None

            if cache:
                guild._add_member(member)
            return member

        # If we're not being rate limited then we can use the websocket to actually query
        members = await guild.query_members(limit=1, user_ids=[user_id], cache=cache)
        if not members:
            return None
        return members[0]

    async def convert(
        self, ctx: commands.Context[bot.AndreiBot], argument: str
    ) -> discord.Member:

        bot = ctx.bot
        match = rx.match(argument) or re.match(r"<@!?([0-9]{15,20})>$", argument)
        guild = ctx.guild
        result = None
        user_id = None

        if match is None:
            # not a mention...
            result = guild.get_member_named(argument)
        else:
            user_id = int(match.group(1))
            result = guild.get_member(user_id)

        def predicate(u: discord.Member) -> bool:
            return u.nick == argument

        result = discord.utils.find(predicate, ctx.guild.members)
        if result:
            return result

        def predicate(u: discord.Member) -> bool:
            return u.nick and u.nick.lower().startswith(argument)

        result = discord.utils.find(predicate, ctx.guild.members)
        if result:
            return result

        def predicate(u: discord.Member) -> bool:
            return u.nick and (argument.lower() in u.nick.lower())

        result = discord.utils.find(predicate, ctx.guild.members)
        if result:
            return result

        def predicate(user: discord.Member) -> bool:
            return str(user).lower().startswith(argument.lower())

        result = discord.utils.find(predicate, ctx.guild.members)
        if result:
            return result

        if not isinstance(result, discord.Member):
            if guild is None:
                raise commands.MemberNotFound(argument)

            if user_id is not None:
                result = await self.query_member_by_id(bot, guild, user_id)
            else:
                result = await self.query_member_named(guild, argument)

            if not result:
                raise commands.MemberNotFound(argument)

        return result


class RoleConverter(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str):
        match = rx.match(argument) or re.match(r"<@&([0-9]{15,20})>$", argument)
        if match:
            result = ctx.guild.get_role(int(match.group(1)))
        else:
            result = discord.utils.get(ctx.guild._roles.values(), name=argument)
        if result is None:
            for role in ctx.guild.roles:
                if role.name.lower() == argument.lower():
                    return role
        if result is None:
            for role in ctx.guild.roles:
                if role.name.lower().startswith(argument.lower()):
                    return role
        if result is None:
            for role in ctx.guild.roles:
                if argument.lower() in role.name.lower():
                    return role
        if result is None:
            raise commands.RoleNotFound(argument)
        return result


class SimpleActivityPageSource(menus.ListPageSource):
    async def format_page(self, menu, entries):
        pages = []
        # one emoji per page
        for index, entry in enumerate(entries, start=menu.current_page * self.per_page):
            pages.append(
                f"{activity_emojis.get(entry['activity'])} {discord.utils.format_dt(entry['datetime'])}"
            )

        maximum = self.get_max_pages()
        if maximum > 1:
            footer = f"Page {menu.current_page + 1}/{maximum}"
            footer += f" ({len(self.entries)} entries)"
            menu.embed.set_footer(text=footer)
        menu.embed.description = "\n".join(pages)
        return menu.embed


class SimpleActivityPages(RoboPages):
    """A simple pagination session reminiscent of the old Pages interface.
    Basically an embed with some normal formatting.
    """

    def __init__(
        self,
        entries,
        *,
        ctx: commands.Context,
        per_page: int = 12,
        user: discord.User,
        text: str,
    ):
        super().__init__(SimpleActivityPageSource(entries, per_page=per_page), ctx=ctx)
        self.embed = discord.Embed(colour=discord.Colour.orange(), title=text)
        self.embed.set_author(name=f"{user}'s activity", icon_url=user.display_avatar)


class SimpleActivityLeaderboardPageSource(menus.ListPageSource):
    async def format_page(self, menu, entries):
        pages = []
        # one emoji per page
        for index, entry in enumerate(entries, start=menu.current_page * self.per_page):

            pages.append(
                f"{index}) {entry[0]} {humanfriendly.format_timespan(entry[1])}"
            )

        maximum = self.get_max_pages()
        if maximum > 1:
            footer = f"Page {menu.current_page + 1}/{maximum}"
            footer += f" ({len(self.entries)} entries)"
            menu.embed.set_footer(text=footer)
        menu.embed.description = "\n".join(pages)
        return menu.embed


class SimpleActivityLeaderboardPages(RoboPages):
    """A simple pagination session reminiscent of the old Pages interface.
    Basically an embed with some normal formatting.
    """

    def __init__(self, entries, *, ctx: commands.Context, per_page: int = 12):
        super().__init__(
            SimpleActivityLeaderboardPageSource(entries, per_page=per_page), ctx=ctx
        )
        self.embed = discord.Embed(
            colour=discord.Colour.orange(), title="Nerd leaderboard"
        )


class SimpleNicknamePageSource(menus.ListPageSource):
    def __init__(self, entries, *, per_page):
        super().__init__(entries, per_page=per_page)
        self.do_show_dates: bool = False

    async def format_page(self, menu, entries):
        menu.embed.description = ""
        for index, entry in enumerate(entries, start=menu.current_page * self.per_page):
            date = discord.utils.format_dt(entry["datetime"], "d")
            name = entry["nickname"]
            new_name = ""
            for character in name:
                if character in ("*", "_", "|", "~", "`"):
                    new_name += chr(92) + character
                else:
                    new_name += character
            menu.embed.description += (
                f"\n{f'{date} ' if self.do_show_dates else ''}{new_name}"
            )

        maximum = self.get_max_pages()
        if maximum > 1:
            footer = (
                f"Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)"
            )
            menu.embed.set_footer(text=footer)

        return menu.embed


class SimpleNicknamePages(RoboPages):
    """A simple pagination session reminiscent of the old Pages interface.
    Basically an embed with some normal formatting.
    """

    def __init__(
        self,
        entries,
        *,
        member: discord.Member,
        ctx: commands.Context,
        per_page: int = 12,
    ) -> None:
        super().__init__(SimpleNicknamePageSource(entries, per_page=per_page), ctx=ctx)
        self.embed = discord.Embed(colour=discord.Colour.orange(), title="nicknames")
        self.embed.set_author(name=member, icon_url=member.display_avatar)

    def fill_items(self) -> None:
        super().fill_items()
        self.add_item(self.toggle_dates)

    @discord.ui.button(label="Toggle dates")
    async def toggle_dates(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        self.source.do_show_dates = not self.source.do_show_dates
        await self.show_checked_page(interaction, self.current_page)


class SimpleUsernamePageSource(menus.ListPageSource):
    def __init__(self, entries, *, per_page):
        super().__init__(entries, per_page=per_page)
        self.do_show_dates: bool = False

    async def format_page(self, menu, entries):
        menu.embed.description = ""
        for index, entry in enumerate(entries, start=menu.current_page * self.per_page):
            date = discord.utils.format_dt(entry["datetime"], "d")
            full_name = f"{entry['username']}#{entry['discriminator']:04}"
            new_name = ""
            for character in full_name:
                if character in ("*", "_", "|", "~", "`"):
                    new_name += chr(92) + character
                else:
                    new_name += character
            menu.embed.description += (
                f"\n{f'{date} ' if self.do_show_dates else ''}{new_name}"
            )
        maximum = self.get_max_pages()
        if maximum > 1:
            footer = (
                f"Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)"
            )
            menu.embed.set_footer(text=footer)

        return menu.embed


class SimpleUsernamePages(RoboPages):
    """A simple pagination session reminiscent of the old Pages interface.
    Basically an embed with some normal formatting.
    """

    def __init__(
        self, entries, *, user: discord.User, ctx: commands.Context, per_page: int = 12
    ) -> None:
        super().__init__(SimpleUsernamePageSource(entries, per_page=per_page), ctx=ctx)
        self.embed = discord.Embed(colour=discord.Colour.orange(), title="usernames")
        self.embed.set_author(name=user, icon_url=user.display_avatar)
        self.source: SimpleUsernamePageSource
        self.source.do_show_dates: bool = False # type: ignore

    def fill_items(self) -> None:
        super().fill_items()
        self.add_item(self.toggle_dates)

    @discord.ui.button(label="Toggle dates")
    async def toggle_dates(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        self.source.do_show_dates = not self.source.do_show_dates
        await self.show_checked_page(interaction, self.current_page)


class SimpleInteractionUsernamePages(InteractionRoboPages):
    """A simple pagination session reminiscent of the old Pages interface.
    Basically an embed with some normal formatting.
    """

    def __init__(
        self,
        entries,
        *,
        user: discord.User,
        interaction: discord.Interaction,
        per_page: int = 12,
        hidden: bool = False,
    ) -> None:
        super().__init__(
            SimpleUsernamePageSource(entries, per_page=per_page),
            interaction=interaction,
            hidden=hidden,
        )
        self.embed = discord.Embed(colour=discord.Colour.orange(), title="usernames")
        self.embed.set_author(name=user, icon_url=user.display_avatar)

    def fill_items(self) -> None:
        if not self.compact:
            self.numbered_page.row = 1
            self.stop_pages.row = 1

        if self.source.is_paginating():
            max_pages = self.source.get_max_pages()
            use_last_and_first = max_pages is not None and max_pages >= 2
            if use_last_and_first:
                self.add_item(self.go_to_first_page)  # type: ignore
            self.add_item(self.go_to_previous_page)  # type: ignore
            if not self.compact:
                self.add_item(self.go_to_current_page)  # type: ignore
            self.add_item(self.go_to_next_page)  # type: ignore
            if use_last_and_first:
                self.add_item(self.go_to_last_page)  # type: ignore
            if not self.compact:
                self.add_item(self.numbered_page)  # type: ignore
            self.add_item(self.stop_pages)  # type: ignore
        self.add_item(self.toggle_dates)

    @discord.ui.button(label="Toggle dates")
    async def toggle_dates(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        self.source.do_show_dates = not self.source.do_show_dates
        await self.show_checked_page(interaction, self.current_page)


class SimpleInteractionNicknamePages(InteractionRoboPages):
    """A simple pagination session reminiscent of the old Pages interface.
    Basically an embed with some normal formatting.
    """

    def __init__(
        self,
        entries,
        *,
        member: discord.Member,
        interaction: discord.Interaction,
        per_page: int = 12,
        hidden: bool = False,
    ) -> None:
        super().__init__(
            SimpleNicknamePageSource(entries, per_page=per_page),
            interaction=interaction,
            hidden=hidden,
        )
        self.embed = discord.Embed(colour=discord.Colour.orange(), title="nicknames")
        self.embed.set_author(name=member, icon_url=member.display_avatar)

    def fill_items(self) -> None:
        if not self.compact:
            self.numbered_page.row = 1
            self.stop_pages.row = 1

        if self.source.is_paginating():
            max_pages = self.source.get_max_pages()
            use_last_and_first = max_pages is not None and max_pages >= 2
            if use_last_and_first:
                self.add_item(self.go_to_first_page)  # type: ignore
            self.add_item(self.go_to_previous_page)  # type: ignore
            if not self.compact:
                self.add_item(self.go_to_current_page)  # type: ignore
            self.add_item(self.go_to_next_page)  # type: ignore
            if use_last_and_first:
                self.add_item(self.go_to_last_page)  # type: ignore
            if not self.compact:
                self.add_item(self.numbered_page)  # type: ignore
            self.add_item(self.stop_pages)  # type: ignore
        self.add_item(self.toggle_dates)

    @discord.ui.button(label="Toggle dates")
    async def toggle_dates(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        self.source.do_show_dates = not self.source.do_show_dates
        await self.show_checked_page(interaction, self.current_page)


class CustomUserTransformer(discord.app_commands.Transformer):
    @property
    def type(self) -> discord.AppCommandOptionType:
        return discord.AppCommandOptionType.user

    async def transform(
        self, interaction: discord.Interaction, value: typing.Any
    ) -> typing.Any:
        return value

    async def convert(self, ctx: commands.Context, current: typing.Any):
        return await UserConverter().convert(ctx, current)


class CustomMemberTransformer(discord.app_commands.transformers.MemberTransformer):
    async def convert(self, ctx: commands.Context, current: str):
        return await MemberConverter().convert(ctx, current)


class CustomRoleTransformer(discord.app_commands.Transformer):
    @property
    def type(self):
        return discord.AppCommandOptionType.role

    async def transform(self, interaction: discord.Interaction, value):
        return value

    async def convert(self, ctx: commands.Context, argument: str):
        match = rx.match(argument) or re.match(r"<@&([0-9]{15,20})>$", argument)
        if match:
            result = ctx.guild.get_role(int(match.group(1)))
        else:
            result = discord.utils.get(ctx.guild._roles.values(), name=argument)
        if result is None:
            for role in ctx.guild.roles:
                if role.name.lower() == argument.lower():
                    return role
        if result is None:
            for role in ctx.guild.roles:
                if role.name.lower().startswith(argument.lower()):
                    return role
        if result is None:
            for role in ctx.guild.roles:
                if argument.lower() in role.name.lower():
                    return role
        if result is None:
            raise commands.RoleNotFound(argument)
        return result


class BirthdayUserTransformer(discord.app_commands.Transformer):
    @property
    def type(self) -> discord.AppCommandOptionType:
        return discord.AppCommandOptionType.string

    async def transform(
        self, interaction: discord.Interaction, value: typing.Any
    ) -> typing.Any:
        mock_ctx = await interaction.client.get_context(interaction)
        return await UserConverter().convert(mock_ctx, value)

    async def convert(self, ctx: commands.Context, current: typing.Any):
        return await UserConverter().convert(ctx, current)

    async def autocomplete(self, interaction: discord.Interaction, current: str):
        complete = []
        done = []
        try:
            userid = str(int(current))
        except ValueError:
            userid = None

        for user in interaction.client.birthdayusers:
            if user.id in done:
                continue
            if current in str(user).lower():
                complete.append(
                    discord.app_commands.Choice(value=str(user.id), name=str(user))
                )
                done.append(user.id)
        if userid:
            for user_id in [str(user.id) for user in interaction.client.birthdayusers]:
                if userid in user_id:
                    if int(userid) in done:
                        continue
                    us = interaction.client.get_user(int(user_id))
                    complete.append(
                        discord.app_commands.Choice(value=str(us.id), name=str(us))
                    )
                    done.append(us.id)

        return complete[:25]


class MusicView(discord.ui.View):
    def __init__(self, bot: bot.AndreiBot):
        super().__init__(timeout=None)
        self.bot = bot

    def get_player(self, guild: discord.Guild) -> lavalink.DefaultPlayer | None:
        return self.bot.lavalink.player_manager.create(guild.id)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        player = self.get_player(interaction.guild)
        if player is None:
            return await interaction.response.send_message(
                content="I'm not currently playing anything!", ephemeral=True
            )
        if not interaction.user.voice:
            return await interaction.response.send_message(
                content="You're not connected to a voice channel!", ephemeral=True
            )
        if not interaction.guild.voice_client:
            return await interaction.response.send_message(
                content="I'm not connected to a voice channel!", ephemeral=True
            )
        if player.channel_id != interaction.user.voice.channel.id:
            return await interaction.response.send_message(
                content="You must be connected to my voice channel", ephemeral=True
            )
        return True

    @discord.ui.button(label="-10s")
    async def _tensback(self, interaction: discord.Interaction, _):
        player = self.get_player(interaction.guild)
        if not player.current and not player.current.is_seekable:
            return await interaction.response.defer()
        await player.seek(player.position - 10000)
        player = self.get_player(interaction.guild)
        song = player.current
        if song is None:
            await interaction.response.defer()
            return await interaction.delete_original_response()
        try:
            current_str = datetime.timedelta(
                seconds=int((player.position - 10000) / 1000)
            )
            full_str = datetime.timedelta(seconds=int(song.duration / 1000))
            res = f"{current_str}/{full_str}"
        except OverflowError:
            res = ""
        em = discord.Embed(color=discord.Color.orange())
        em.set_author(name=interaction.user, icon_url=interaction.user.display_avatar)
        em.title = "went 10s back"
        em.description = f"[{song.title}]({song.uri}) {res}"
        await interaction.response.edit_message(embed=em, view=self)

    @discord.ui.button(label="Pause/Play", style=discord.ButtonStyle.blurple)
    async def _playbutton(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        player = self.get_player(interaction.guild)
        new = not player.paused
        await player.set_pause(new)
        em = discord.Embed(color=discord.Color.orange())
        em.set_author(name=interaction.user, icon_url=interaction.user.display_avatar)
        song = player.current
        if song is None:
            await interaction.response.defer()
            return
        try:
            current_str = datetime.timedelta(seconds=int((player.position) / 1000))
            full_str = datetime.timedelta(seconds=int(song.duration / 1000))
            res = f"{current_str}/{full_str}"
        except OverflowError:
            res = ""
        await player.set_pause(new)
        if new:
            em.title = "resumed"
            button.label = "pause"
        else:
            em.title = "paused"
            button.label = "play"
        em.description = f"[{song.title}]({song.uri}) {res}"
        await interaction.response.edit_message(embed=em, view=self)

    @discord.ui.button(label="+10s")
    async def _skiptens(self, interaction: discord.Interaction, _):
        player = self.get_player(interaction.guild)
        if not player.current and not player.current.is_seekable:
            return await interaction.response.defer()
        await player.seek(player.position + 10000)
        player = self.get_player(interaction.guild)
        song = player.current
        if song is None:
            await interaction.response.defer()
            return await interaction.delete_original_response()
        try:
            current_str = datetime.timedelta(
                seconds=int((player.position + 10000) / 1000)
            )
            full_str = datetime.timedelta(seconds=int(song.duration / 1000))
            res = f"{current_str}/{full_str}"
        except OverflowError:
            res = ""
        em = discord.Embed(color=discord.Color.orange())
        em.set_author(name=interaction.user, icon_url=interaction.user.display_avatar)
        em.title = "skipped 10s"
        em.description = f"[{song.title}]({song.uri}) {res}"
        await interaction.response.edit_message(embed=em, view=self)

    @discord.ui.button(label="Skip", row=1)
    async def _skipbutton(self, interaction: discord.Interaction, _):
        player = self.get_player(interaction.guild)
        await player.play()
        player = self.get_player(interaction.guild)
        song = player.current
        if song is None:
            await interaction.response.defer()
            return await interaction.delete_original_response()
        em = discord.Embed(color=discord.Color.orange(), title=f"Skipped")
        em.set_author(name=interaction.user, icon_url=interaction.user.display_avatar)
        em.description = f"Now playing [{song.title}]({song.uri})"
        await interaction.response.edit_message(embed=em, view=self)

    @discord.ui.button(label="Update", row=1)
    async def _updatebutton(self, interaction: discord.Interaction, _):
        player = self.get_player(interaction.guild)
        song = player.current
        if song is None:
            em = discord.Embed(color=discord.Color.orange(), title=f"Currently playing")
            em.description = "Playing nothing"
            return await interaction.response.edit_message(embed=em)
        try:
            current_str = datetime.timedelta(seconds=int((player.position) / 1000))
            full_str = datetime.timedelta(seconds=int(song.duration / 1000))
            res = f"{current_str}/{full_str}"
        except OverflowError:
            res = ""
        em = discord.Embed(color=discord.Color.orange(), title=f"Currently playing")
        em.set_author(name=interaction.user, icon_url=interaction.user.display_avatar)
        em.description = f"[{song.title}]({song.uri}) {res}"
        await interaction.response.edit_message(embed=em, view=self)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red, row=1)
    async def _leavebutton(self, interaction: discord.Interaction, _):
        player = self.get_player(interaction.guild)
        player.queue.clear()
        await player.stop()
        await interaction.guild.voice_client.disconnect(force=True)
        await interaction.response.defer()
        await interaction.delete_original_response()


class LavalinkVoiceClient(discord.VoiceClient):
    """
    This is the preferred way to handle external voice sending
    This client will be created via a cls in the connect method of the channel
    see the following documentation:
    https://discordpy.readthedocs.io/en/latest/api.html#voiceprotocol
    """

    def __init__(self, client: bot.AndreiBot, channel: discord.abc.Connectable):
        self.client = client
        self.channel = channel
        self.lavalink = client.lavalink

    async def on_voice_server_update(self, data):
        # the data needs to be transformed before being handed down to
        # voice_update_handler
        lavalink_data = {"t": "VOICE_SERVER_UPDATE", "d": data}
        await self.lavalink.voice_update_handler(lavalink_data)

    async def on_voice_state_update(self, data):
        # the data needs to be transformed before being handed down to
        # voice_update_handler
        lavalink_data = {"t": "VOICE_STATE_UPDATE", "d": data}
        await self.lavalink.voice_update_handler(lavalink_data)

    async def connect(
        self,
        *,
        timeout: float,
        reconnect: bool,
        self_deaf: bool = False,
        self_mute: bool = False,
    ) -> None:
        """
        Connect the bot to the voice channel and create a player_manager
        if it doesn't exist yet.
        """
        # ensure there is a player_manager when creating a new voice_client
        self.lavalink.player_manager.create(guild_id=self.channel.guild.id)
        await self.channel.guild.change_voice_state(
            channel=self.channel, self_mute=self_mute, self_deaf=self_deaf
        )

    async def disconnect(self, *, force: bool = False) -> None:
        """
        Handles the disconnect.
        Cleans up running player and leaves the voice client.
        """
        player: lavalink.DefaultPlayer | None = self.lavalink.player_manager.get(
            self.channel.guild.id
        )
        if player is not None:
            await player.stop()
            player.queue.clear()
            player.channel_id = None
            self.cleanup()
        await self.channel.guild.change_voice_state(channel=None)


class TrackConverter(commands.Converter):
    async def convert(self, ctx: commands.Context[bot.AndreiBot], query: str):
        player: lavalink.DefaultPlayer = ctx.bot.lavalink.player_manager.create(
            ctx.guild.id
        )
        query = query.strip("<>")
        load_spotify_playlist = False
        self.to_return = 0
        if spotify_rx.search(query):
            if "track" in query:
                song = sp.track(query)
                query = f'{song["name"]} {song["artists"][0]["name"]} lyrics'
            elif "playlist" in query:
                load_spotify_playlist = True
                songsearch = []
                playlist = sp.playlist(query)
                results = playlist["tracks"]
                tracks: list = results["items"]
                while results["next"]:
                    results = sp.next(results)
                    tracks.extend(results["items"])
                for song in tracks:
                    song = song["track"]
                    song_name = song["name"]
                    song_artist = song["artists"][0]["name"]
                    songsearch.append(f"ytsearch:{song_name} {song_artist}")
        if not url_rx.match(query):
            query = f"ytsearch:{query}"

        async def _inner_playlist(__query, current: int):
            results: lavalink.LoadResult = await player.node.get_tracks(__query)
            if not results or not results.tracks:
                return None
            track = results.tracks[0]
            track = lavalink.models.AudioTrack(track, ctx.author.id, recommended=True)
            player.add(track, ctx.author.id)
            self.to_return += 1
            if (current == 0) and not player.is_playing:
                await player.play()

        if load_spotify_playlist:
            coro_list = []
            for i, k in enumerate(songsearch):
                coro_list.append(_inner_playlist(k, i))
            async with ctx.typing():
                await asyncio.gather(*coro_list)
        else:
            results: lavalink.LoadResult = await player.node.get_tracks(query)
            if not results or not results.tracks:
                raise commands.BadArgument("I couldn't find anything")
            if results.load_type == lavalink.LoadType.PLAYLIST:
                for track in results.tracks:
                    player.add(track, ctx.author.id)
                    self.to_return += 1
            else:
                self.to_return += 1
                player.add(results.tracks[0], ctx.author.id)

        if not self.to_return:
            raise commands.BadArgument("I couldn't find anything")
        return self.to_return


class RadioTransformer(discord.app_commands.Transformer):
    async def transform(self, interaction: discord.Interaction, value: str) -> str:
        return value

    async def autocomplete(self, interaction: discord.Interaction, value: str):
        to_return = []
        _bot: bot.AndreiBot = interaction.client
        for radio in _bot.radios.values():
            if value.lower() in radio["title"].lower():
                to_return.append(
                    discord.app_commands.Choice(name=radio["title"], value=radio["id"])
                )
        return to_return[:25]


async def get_user_reference(message: discord.Message) -> None | discord.User:
    if message is None:
        return None
    if message.reference is None:
        return None
    if message.reference.cached_message:
        return message.reference.cached_message.author
    message_id = message.reference.message_id
    try:
        reference = await message.channel.fetch_message(message_id)
    except (discord.Forbidden, discord.NotFound, discord.HTTPException):
        return None
    if isinstance(reference.author, discord.User):
        return reference.author
    return message._state.get_user(reference.author.id)


async def get_member_reference(message: discord.Message) -> None | discord.Member:
    if message is None:
        return None
    if message.reference is None:
        return None
    if message.reference.cached_message:
        return message.reference.cached_message.author
    message_id = message.reference.message_id
    try:
        reference = await message.channel.fetch_message(message_id)
    except (discord.Forbidden, discord.NotFound, discord.HTTPException):
        return None
    return message.guild.get_member(reference.author.id)


async def get_reference(
    message: discord.Message,
) -> None | discord.User | discord.Member:
    if message is None:
        return None
    if message.reference is None:
        return None
    if message.reference.cached_message:
        return message.reference.cached_message.author
    message_id = message.reference.message_id
    try:
        reference = await message.channel.fetch_message(message_id)
    except (discord.Forbidden, discord.NotFound, discord.HTTPException):
        return None
    return reference.author


class AutoDownloadView(ConfirmationView):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.ctx.author:
            return True

        elif interaction.user.guild_permissions.administrator:
            return True
        elif interaction.user.id in interaction.client.owner_ids:
            return True
        elif (
            interaction.channel.permissions_for(interaction.user).embed_links
            and interaction.channel.permissions_for(interaction.user).manage_messages
        ):
            return True
        else:
            return await interaction.response.send_message(
                "This button isn't for you", ephemeral=True
            )


class TikTokPageSource(menus.ListPageSource):
    def __init__(self, entries, *, per_page, author: discord.User):
        super().__init__(entries, per_page=per_page)
        self.author = author

    async def format_page(self, menu: menus.Menu, entry):
        maximum = self.get_max_pages()
        if maximum > 1:
            footer = f"Page {menu.current_page + 1}/{maximum}"
            menu.embed.set_footer(text=footer)
        menu.embed.set_author(name=self.author, icon_url=self.author.display_avatar)
        menu.embed.set_image(url=entry)
        return menu.embed
