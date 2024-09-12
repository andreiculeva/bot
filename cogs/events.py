import re
import discord
from discord.ext import commands, tasks
import asyncio
import typing
import bot
import traceback
import utils
from discord.ext.commands.errors import (
    CommandNotFound,
    MemberNotFound,
    MissingPermissions,
    MissingRequiredArgument,
    RoleNotFound,
    UserNotFound,
)


def is_valid_url(url: str):
    valid_re = [
        re.compile(
            r"https?://www\.tiktok\.com/(?:embed|@(?P<user_id>[\w\.-]+)/video)/(?P<id>\d+)"
        ),
        re.compile(r"https?://(?:vm|vt)\.tiktok\.com/(?P<id>\w+)"),
        re.compile(r"https?://(?:www\.)?tiktok\.com/@(?P<id>[\w\.-]+)/?(?:$|[#?])"),
        re.compile(r"https?://(?:www\.)?douyin\.com/video/(?P<id>[0-9]+)"),
    ]
    for regex in valid_re:
        if match := regex.search(url):
            return match.group(0)
    if (m := utils.url_rx.search(url)) and ("instagram" in url):
        return m.group(0)  # instagram
    return None


class events(commands.Cog):
    def __init__(self, bot: bot.AndreiBot):
        self.bot = bot

        self.vanities: dict[int, discord.Invite] = {}
        self.invites = {}
        self.channels = {}  # server_id : channel_id
        self.update_invites.start()

    def cog_unload(self):
        self.update_invites.cancel()

    @staticmethod
    @commands.Cog.listener()
    async def on_command_error(ctx: commands.Context[bot.AndreiBot], error):
        if hasattr(ctx.command, "on_error"):
            return
        if ctx.cog:
            if ctx.cog._get_overridden_method(ctx.cog.cog_command_error) is not None:
                return
        em = discord.Embed(color=discord.Color.red())
        error = getattr(error, "original", error)
        if isinstance(error, CommandNotFound):
            if (
                ctx.author.id in (bot.ANDREI2_ID, bot.ANDREI_ID)
                and ctx.guild.id == 831556458398089217
            ):
                em.description = f"I couldn't find that command"
                await ctx.send(embed=em, ephemeral=True)
            return

        if isinstance(error, UserNotFound):
            em.description = f"I couldn't find the user `{error.argument}`"
        elif isinstance(error, MemberNotFound):
            em.description = f"I couldn't find `{error.argument}` in the server"
        elif isinstance(error, MissingRequiredArgument):
            em.description = (
                f"`{error.param.name}` is a required argument that is missing"
            )
        elif isinstance(error, discord.Forbidden):
            em.description = f"I am missing permissions"
        elif isinstance(error, MissingPermissions):
            if ctx.author.id in ctx.bot.owner_ids:
                await ctx.reinvoke(restart=True)  # bypass owners
                return
            x = ", ".join(
                [f"`{p.replace('_', ' ')}`" for p in error.missing_permissions]
            )
            em.description = f"You are missing the {x} perms"
        elif isinstance(error, RoleNotFound):
            em.description = (
                f"I couldn't find the role `{error.argument}` in this server"
            )
        elif isinstance(error, discord.HTTPException):
            em.add_field(
                name="HTTP exception", value=f"error code {error.code}\n{error.text}"
            )
        elif isinstance(error, commands.BadLiteralArgument):
            em.description = (
                f"{error.param} is not a valid argument ({' ,'.join(error.literals)})"
            )
        elif isinstance(error, commands.EmojiNotFound):
            em.add_field(
                name="Couldn't find that emoji", value="Maybe I am not in that server"
            )
        elif isinstance(error, commands.PartialEmojiConversionFailure):
            em.description = "I couldn't find that emoji"
        elif isinstance(error, ValueError):
            em.description = f"{error.args[0]}"
        elif isinstance(error, commands.BadArgument):
            em.description = str(error)
        elif isinstance(error, commands.CommandInvokeError):
            em.description = str(error)
        else:
            if ctx.author.id in (bot.ANDREI2_ID, bot.ANDREI_ID):
                if isinstance(error, str):  # ??
                    em.description = str(error)
                else:
                    lines = traceback.format_exception(
                        type(error), error, error.__traceback__
                    )
                    traceback_text = "".join(lines)
                    em.description = f"```python\n{traceback_text}```"
            else:
                em.description = str(error)
        await ctx.send(embed=em, ephemeral=True)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        em = discord.Embed(
            color=discord.Color.green(),
            description=f"Joined a new Server\nOwner: {guild.owner} - {guild.owner_id}\nMembers: {guild.member_count} - Roles: {len(guild.roles)} - Channels: {len(guild.text_channels) + len(guild.voice_channels)}",
        )
        em.set_footer(text=f"Server ID: {guild.id}")
        em.set_image(url=guild.icon)
        em.set_author(name=f"{guild.name}", icon_url=guild.icon)
        await self.bot.log_channel.send(embed=em)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        em = discord.Embed(
            color=discord.Color.red(),
            description=f"Left a Server\nOwner: {guild.owner.name}#{guild.owner.discriminator} - {guild.owner_id}\nMembers: {guild.member_count} - Roles: {len(guild.roles)} - Channels: {len(guild.text_channels) + len(guild.voice_channels)}",
        )
        em.set_footer(text=f"Server ID: {guild.id}")
        em.set_image(url=guild.icon)
        em.set_author(name=f"{guild.name}", icon_url=guild.icon)
        await self.bot.log_channel.send(embed=em)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot:
            return
        author_reference = 0
        message_reference = 0
        if message.reference:
            if message.reference.resolved:
                author_reference = message.reference.resolved.author.id
                message_reference = message.reference.resolved.id
            else:
                try:
                    _message = await message.channel.fetch_message(
                        message.reference.message_id
                    )
                    author_reference = _message.author.id
                    message_reference = _message.id
                except (discord.NotFound, discord.HTTPException):
                    pass

        newreq = "INSERT into deleted_messages (server_id, channel_id, message_id, author_id, datetime, message_content, reference_message_id, reference_author_id) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)"
        if message.content:
            mc = message.content
        else:
            mc = "This message had no content"
        await self.bot.pool.execute(
            newreq,
            message.guild.id,
            message.channel.id,
            message.id,
            message.author.id,
            message.created_at,
            mc,
            message_reference,
            author_reference,
        )
        if message.attachments:
            attachment = message.attachments[0]
            filebytes = await attachment.read()
            self.bot.deleted_files[message.id] = (filebytes, attachment.filename)

            await asyncio.sleep(600)
            self.bot.deleted_files.pop(message.id, None)

    @commands.Cog.listener(name="on_message")
    async def counter(self, message: discord.Message):
        if message.channel.id not in (928597369111576597, 715986355485933619):
            return
        if (
            message.attachments
            or message.components
            or message.embeds
            or message.stickers
        ):
            return await message.delete()
        if not message.content:
            return await message.delete()
        async for last_message in message.channel.history(
            before=message.created_at, limit=1
        ):
            pass
        if message.author.id == last_message.author.id:
            return await message.delete()
        try:
            vals = ["*", "_", " "]
            c = message.content
            for val in vals:
                if c.startswith(val) and c.endswith(val):
                    c = c.replace(val, "")
            number = int(c)
        except ValueError:
            return await message.delete()
        old_number = int(last_message.content)
        if number != (old_number + 1):
            await message.delete()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not message.guild:
            if message.author.id in (393033826474917889,):  # andrei id
                return
            member = message.author
            log = self.bot.log_channel
            if message.content == "":
                em = discord.Embed(color=discord.Color.orange())
            else:
                em = discord.Embed(
                    description=message.content, color=discord.Color.orange()
                )
            em.set_author(
                name=member,
                icon_url=member.avatar if (member.avatar) else member.display_avatar,
                url=member.avatar if (member.avatar) else member.display_avatar,
            )
            em.set_footer(text="user id: {}".format(member.id))

            if len(message.attachments) == 1:
                file_type = message.attachments[0].filename.split(".")[-1].lower()
                if (
                    file_type == "png"
                    or file_type == "jpeg"
                    or file_type == "jpg"
                    or file_type == "gif"
                ):
                    # set as embed image
                    em.set_image(url=message.attachments[0].proxy_url)
                    await log.send(embed=em)
                else:
                    if message.attachments[0].size > 8388608:
                        return
                    file = await message.attachments[0].to_file()
                    # send file as attachment

                    await log.send(embed=em)
                    await log.send(file=file)

            elif len(message.attachments) > 1:
                await log.send(embed=em)
                for ATTACHMENT in message.attachments:
                    temp_embed = discord.Embed(
                        description=f"multiple files from: {member}",
                        color=discord.Color.orange(),
                    )
                    temp_embed.set_author(
                        name=member,
                        icon_url=(
                            member.avatar if (member.avatar) else member.display_avatar
                        ),
                        url=member.avatar if (member.avatar) else member.display_avatar,
                    )
                    temp_embed.set_footer(text=f"user id : {member.id}")
                    file_type = ATTACHMENT.filename.split(".")[-1].lower()
                    if (
                        file_type == "png"
                        or file_type == "jpeg"
                        or file_type == "jpg"
                        or file_type == "gif"
                    ):
                        temp_embed.set_image(url=ATTACHMENT.proxy_url)
                        await log.send(embed=temp_embed)
                    else:
                        if ATTACHMENT.size > 8388608:
                            continue
                        file = await ATTACHMENT.to_file()
                        await log.send(embed=temp_embed)
                        await log.send(file=file)
            else:
                await log.send(embed=em)

            return

        if discord.utils.get(message.author.roles, name="blacklisted"):
            await message.delete()

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: list[discord.Message]):
        for message in messages:
            author_reference = 0
            message_reference = 0
            if message.reference:
                if message.reference.resolved:
                    author_reference = message.reference.resolved.author.id
                    message_reference = message.reference.resolved.id
                else:
                    try:
                        _message = await message.channel.fetch_message(
                            message.reference.message_id
                        )
                        author_reference = _message.author.id
                        message_reference = _message.id
                    except (discord.NotFound, discord.HTTPException):
                        pass
            newreq = "INSERT into deleted_messages (server_id, channel_id, message_id, author_id, datetime, message_content, reference_message_id, reference_author_id) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)"
            if message.content:
                mc = message.content
            else:
                mc = "This message had no content"
            ts = message.created_at
            await self.bot.pool.execute(
                newreq,
                message.guild.id,
                message.channel.id,
                message.id,
                message.author.id,
                ts,
                mc,
                message_reference,
                author_reference,
            )

    @commands.Cog.listener(name="on_raw_reaction_add")
    async def _starboard_checker(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id in ():  # blacklisted guilds?
            return
        if str(payload.emoji) != "\U00002b50":
            return
        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            return
        starboard_channel = discord.utils.find(
            lambda t: t.name.lower() == "starboard", channel.guild.text_channels
        )
        if starboard_channel is None:
            return
        try:
            message = await channel.fetch_message(payload.message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return
        pin = False
        for reaction in message.reactions:
            if str(reaction.emoji) == "\U00002b50":
                async for user in reaction.users(limit=None):
                    if user.guild:
                        if user.guild_permissions.administrator:
                            pin = True
                count = reaction.count
                break
            else:
                count = 0
        if (count < 3) and not pin:
            return
        em = discord.Embed(color=discord.Color.orange())
        em.title = f"{count} \U00002b50"
        content = f"[Jump URL]({message.jump_url})\n"
        content += message.content
        em.set_author(
            name=message.author.display_name, icon_url=message.author.display_avatar.url
        )
        em.timestamp = message.created_at
        em.set_footer(text=f"ID: {message.id}")
        image_set = False
        if len(message.attachments) == 1:
            if (
                message.attachments[0]
                .url.lower()
                .endswith(("png", "jpeg", "jpg", "gif", "webp"))
            ):
                em.set_image(url=message.attachments[0].url)
                image_set = True
            else:
                em.add_field(
                    name="Attachment",
                    value=f"[{message.attachments[0].filename}]({message.attachments[0].url})",
                )

        else:
            for attachment in message.attachments:
                if attachment.url.lower().endswith(
                    ("png", "jpeg", "jpg", "gif", "webp")
                ):
                    if not image_set:
                        em.set_image(url=attachment.url)
                        image_set = True
                        continue
                em.add_field(
                    name="Attachment",
                    value=f"[{attachment.filename}]({attachment.url})",
                )
        if message.stickers:
            if not image_set:
                em.set_image(url=message.stickers[0].url)
            content += f"\nMessage has {len(message.stickers)} stickers"
        em.description = content
        star_id = await self.bot.pool.fetchval(
            f"SELECT star_message_id FROM star_messages WHERE original_message_id={message.id}"
        )
        if star_id:
            try:
                star_message = await starboard_channel.fetch_message(star_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return
            return await star_message.edit(embed=em)
        m = await starboard_channel.send(embed=em)
        await self.bot.pool.execute(
            f"INSERT INTO star_messages (original_message_id, star_message_id) VALUES ({message.id}, {m.id})"
        )

    @commands.Cog.listener(name="on_raw_reaction_remove")
    async def _remove_star(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id in ():  # blacklisted guilds??
            return

        if str(payload.emoji) != "\U00002b50":
            return
        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            return
        starboard_channel = discord.utils.find(
            lambda t: t.name.lower() == "starboard", channel.guild.text_channels
        )
        if starboard_channel is None:
            return
        try:
            message = await channel.fetch_message(payload.message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return
        pin = False
        count = 0
        for reaction in message.reactions:
            if str(reaction.emoji) == "\U00002b50":
                async for user in reaction.users(limit=None):
                    if user.guild:
                        if user.guild_permissions.administrator:
                            pin = True
                count = reaction.count
                break
            else:
                count = 0
        if count < 3:
            if pin:
                return
            star_id = await self.bot.pool.fetchval(
                f"SELECT star_message_id FROM star_messages WHERE original_message_id={message.id}"
            )
            if star_id:
                try:
                    star_message = await starboard_channel.fetch_message(star_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    return
                await star_message.delete()
                await self.bot.pool.execute(
                    f"DELETE FROM star_messages WHERE original_message_id={message.id}"
                )
                return
        else:
            em = discord.Embed(color=discord.Color.orange())
            em.title = f"{count} \U00002b50"
            content = f"[Jump URL]({message.jump_url})\n"
            content += message.content
            em.set_author(
                name=message.author.display_name, icon_url=message.author.display_avatar
            )
            em.timestamp = message.created_at
            em.set_footer(text=f"ID: {message.id}")
            image_set = False
            if len(message.attachments) == 1:
                if (
                    message.attachments[0]
                    .url.lower()
                    .endswith(("png", "jpeg", "jpg", "gif", "webp"))
                ):
                    em.set_image(url=message.attachments[0].url)
                    image_set = True
                else:
                    em.add_field(
                        name="Attachment",
                        value=f"[{message.attachments[0].filename}]({message.attachments[0].url})",
                    )

            else:
                for attachment in message.attachments:
                    if attachment.url.lower().endswith(
                        ("png", "jpeg", "jpg", "gif", "webp")
                    ):
                        if not image_set:
                            em.set_image(url=attachment.url)
                            image_set = True
                            continue
                    em.add_field(
                        name="Attachment",
                        value=f"[{attachment.filename}]({attachment.url})",
                    )
            if message.stickers:
                if not image_set:
                    em.set_image(url=message.stickers[0].url)
                content += f"\nMessage has {len(message.stickers)} stickers"
            em.description = content
            star_id = await self.bot.pool.fetchval(
                f"SELECT star_message_id FROM star_messages WHERE original_message_id={message.id}"
            )
            if star_id:
                try:
                    star_message = await starboard_channel.fetch_message(star_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    return
                await star_message.edit(embed=em)

    @commands.Cog.listener("on_message_edit")
    async def _editlogger(self, before: discord.Message, after: discord.Message):
        if before.content == after.content:
            return
        if before.author.bot:
            return
        query = "INSERT into edited_messages (server_id, channel_id, message_id, message_content, datetime, author_id) VALUES ($1, $2, $3, $4, $5, $6)"
        if before.edited_at is None:
            # original message
            await self.bot.pool.execute(
                query,
                before.guild.id,
                before.channel.id,
                before.id,
                before.content,
                before.created_at,
                before.author.id,
            )
        await self.bot.pool.execute(
            query,
            before.guild.id,
            before.channel.id,
            before.id,
            after.content,
            after.edited_at,
            before.author.id,
        )

    @tasks.loop(minutes=10)
    async def update_invites(self):
        data = await self.bot.pool.fetch("SELECT * FROM invite_logchannel")
        if not data:
            return
        self.channels = {}
        for server_id, channel_id in data:
            self.channels[server_id] = channel_id

        # list of the old server invites
        invite_servers = list(self.invites.keys())
        for server_id in invite_servers:
            if server_id not in self.channels.keys():
                del self.invites[server_id]
                del self.vanities[server_id]

        for server_id, channel_id in self.channels.items():
            self.invites[server_id] = await self.bot.get_guild(server_id).invites()

        for server_id, channel_id in self.channels.items():
            try:
                self.vanities[server_id] = await self.bot.get_guild(
                    server_id
                ).vanity_invite()
            except discord.Forbidden:
                self.vanities[server_id] = None

    @update_invites.before_loop
    async def waiter(self):
        await self.bot.wait_until_ready()
        data = await self.bot.pool.fetch("SELECT * FROM invite_logchannel")
        if not data:
            return
        for server_id, channel_id in data:
            self.channels[server_id] = channel_id
            log_channel = self.bot.get_channel(channel_id)
            self.invites[server_id] = await log_channel.guild.invites()
            try:
                self.vanities[server_id] = await log_channel.guild.vanity_invite()
            except discord.Forbidden:
                self.vanities[server_id] = None

    def find_invite_by_code(
        self, inv_list: list[discord.Invite]
    ) -> typing.Optional[discord.Invite]:
        for new_invite in inv_list:
            for old_invite in self.invites[new_invite.guild.id]:
                if new_invite.code == old_invite.code:
                    if new_invite.uses > old_invite.uses:
                        return new_invite  # if use incremented
                if not (old_invite in self.invites[new_invite.guild.id]):
                    return old_invite  # if an old invite is not in the new list anymore
        return None

    @commands.Cog.listener(name="on_member_join")
    async def joinertracker(self, member: discord.Member):
        if not member.guild.id in self.channels.keys():
            return
        em = discord.Embed(color=discord.Color.orange())
        em.set_author(name=member, icon_url=member.display_avatar)
        new_invites = await member.guild.invites()
        vanity = self.vanities[member.guild.id]
        invite = self.find_invite_by_code(new_invites)
        if invite:
            em.description = f"ID: {member.id}\nJoined with: <{invite.url}>\nInviter: {invite.inviter} - {invite.inviter.mention}"

        elif vanity is not None:
            new_vanity = None
            try:
                new_vanity = await member.guild.vanity_invite()
            except discord.Forbidden:
                new_vanity = None
            if new_vanity is None:
                em.description = f"I couldn't figure out how they joiend"
            else:
                if vanity.uses < new_vanity.uses:
                    em.description = (
                        f"Joined with the vanity URL (.gg/{new_vanity.code})"
                    )
                    self.vanities[member.guild.id] = new_vanity
                else:
                    em.description = f"I couldn't figure out how they joiend"
        else:
            em.description = f"I couldn't figure out how they joiend"
        em.description += (
            f"\nAccount created: {discord.utils.format_dt(member.created_at, 'R')}"
        )
        await self.bot.get_channel(self.channels[member.guild.id]).send(embed=em)
        self.invites[member.guild.id] = await member.guild.invites()

    @commands.Cog.listener(name="on_member_remove")
    async def memberremovercheckidk(self, member: discord.Member):
        if not member.guild.id in self.channels.keys():
            return
        em = discord.Embed(color=discord.Color.red())
        em.set_author(name=member, icon_url=member.display_avatar)
        em.description = f"`{member.id}` left the server"
        em.description += (
            f"\nAccount created: {discord.utils.format_dt(member.created_at, 'R')}"
        )
        await self.bot.get_channel(self.channels[member.guild.id]).send(embed=em)
        self.invites[member.guild.id] = await member.guild.invites()

    @commands.Cog.listener(name="on_invite_create")
    async def inviteupdatecreate(self, invite: discord.Invite):
        if not invite.guild.id in self.channels.keys():
            return
        self.invites[invite.guild.id] = await invite.guild.invites()

    @commands.Cog.listener(name="on_invite_delete")
    async def inviteupdatedelete(self, invite: discord.Invite):
        if not invite.guild.id in self.channels.keys():
            return
        self.invites[invite.guild.id] = await invite.guild.invites()

    @commands.Cog.listener(name="on_user_update")
    async def username_logger(self, before: discord.User, after: discord.User):
        """as the name says it logs username changes"""
        if (before.name == after.name) and (
            before.discriminator == after.discriminator
        ):
            return

        await self.bot.pool.execute(
            "INSERT INTO usernames (user_id, datetime, username, discriminator) VALUES ($1, CURRENT_TIMESTAMP, $2, $3)",
            before.id,
            after.name,
            int(after.discriminator),
        )

    @commands.Cog.listener(name="on_member_update")
    async def nickname_logger(self, before: discord.Member, after: discord.Member):
        """As the name says this logs nickname changes"""
        if before.nick == after.nick:
            return
        if after.nick is None:
            return
        await self.bot.pool.execute(
            "INSERT INTO nicknames (server_id, user_id, datetime, nickname) VALUES ($1, $2, CURRENT_TIMESTAMP, $3)",
            after.guild.id,
            after.id,
            after.nick,
        )

    

    # TODO make this work in all servers
    @commands.Cog.listener(name="on_member_update")
    async def _member_stalker(self, before: discord.Member, after: discord.Member):
        return
        channel = self.bot.get_channel(978641097087651840)  # log in test server
        if before.guild.id != channel.guild.id:
            return
        em = discord.Embed(
            color=discord.Color.orange(), description="updated their server profile"
        )
        em.set_author(name=after, icon_url=after.display_avatar)
        em.set_footer(text=f"ID: {after.id}")
        if before.nick != after.nick:
            em.add_field(name="nickname", value=f"{before.nick} -> {after.nick}")
        if before.guild_avatar != after.guild_avatar:
            before_av, after_av = before.guild_avatar, after.guild_avatar
            await asyncio.sleep(5)
            if before_av:
                before_av = (
                    f"{before_av.key}.{'gif' if before_av.is_animated() else 'png'}"
                )
                before_av = await self.bot.pool.fetchval(
                    "SELECT avatar_url FROM avatars WHERE avatar_name = $1", before_av
                )
            if after_av:
                after_av = (
                    f"{after_av.key}.{'gif' if after_av.is_animated() else 'png'}"
                )
                after_av = await self.bot.pool.fetchval(
                    "SELECT avatar_url FROM avatars WHERE avatar_name = $1", after_av
                )
            em.add_field(
                name="server avatar",
                value=f"{f'[before]({before_av})' if before_av else 'None'} -> {f'[after]({after_av})' if after_av else 'None'}",
            )
        if not em.fields:
            return
        await channel.send(embed=em)

    # TODO remake this for all servers maybe
    @commands.Cog.listener(name="on_user_update")
    async def _profile_stalker(self, before: discord.User, after: discord.User):
        return
        channel = self.bot.get_channel(978641097087651840)  # log in test server
        if before.id == self.bot.user.id:
            return
        if channel.guild.get_member(before.id) is None:
            return
        em = discord.Embed(
            color=discord.Color.orange(), description="updated their profile"
        )
        em.set_author(name=after, icon_url=after.display_avatar)
        em.set_footer(text=f"ID: {after.id}")
        if before.name != after.name:
            em.add_field(name="userame", value=f"{before.name} -> {after.name}")
        if before.discriminator != after.discriminator:
            em.add_field(
                name="discriminator",
                value=f"#{before.discriminator} -> #{after.discriminator}",
            )
        if before.avatar != after.avatar:
            before_av, after_av = None, None
            await asyncio.sleep(5)
            if before.avatar:
                before_av = f"{before.avatar.key}.{'gif' if before.avatar.is_animated() else 'png'}"
                before_av = await self.bot.pool.fetchval(
                    "SELECT avatar_url FROM avatars WHERE avatar_name = $1", before_av
                )
            if after.avatar:
                after_av = f"{after.avatar.key}.{'gif' if after.avatar.is_animated() else 'png'}"
                after_av = await self.bot.pool.fetchval(
                    "SELECT avatar_url FROM avatars WHERE avatar_name = $1", after_av
                )
            em.add_field(
                name="avatar",
                value=f"{f'[before]({before_av})' if before_av else 'None'} -> {f'[after]({after_av})' if after_av else 'None'}",
            )
        if not em.fields:
            return
        await channel.send(embed=em)


async def setup(bot: bot.AndreiBot):
    await bot.add_cog(events(bot))
