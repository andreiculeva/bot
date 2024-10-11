import typing
from discord.ext import commands, tasks
import discord
import datetime
from typing import Optional
import re
import humanfriendly
import utils
import contextlib
import bot


async def sanitize_targets(
    ctx: commands.Context, members: list[typing.Union[discord.User, discord.Member]]
) -> list[typing.Union[discord.User, discord.Member]]:
    to_return = []
    pending = []
    for member in members:
        if isinstance(member, discord.User):
            to_return.append(member)
        elif isinstance(member, discord.Member):
            if (
                member.guild_permissions.moderate_members
                or member.guild_permissions.kick_members
                or member.guild_permissions.ban_members
                or member.guild_permissions.manage_messages
            ):
                pending.append(member)
            else:
                to_return.append(member)
        else:
            to_return.append(member)
    if not pending:
        return to_return
    view = utils.ConfirmationView(ctx=ctx)
    embed = discord.Embed(color=discord.Color.red(), title="Warning")
    ass = ", ".join([str(k) for k in pending])
    embed.description = f"There are potential moderators in the converted list ({ass}) do you want to include them anyway?"
    m = await ctx.send(view=view, embed=embed)
    await view.wait()
    try:
        await m.delete()
    except (discord.HTTPException, discord.Forbidden):
        pass
    if not view.value:
        return to_return
    return [*to_return, *pending]


rx = re.compile(r"([0-9]{15,20})$")


class RemoveRoleConverter(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str):
        match = rx.match(argument) or re.match(r"<@&([0-9]{15,20})>$", argument)
        if match:
            result = discord.utils.get(ctx.guild.roles, id=int(match.group(1)))
        else:
            result = discord.utils.get(ctx.guild.roles, name=argument)
        if result is None:
            for role in ctx.guild.roles:
                if role.name.lower() == argument:
                    return role
        if result is None:
            for role in ctx.guild.roles:
                if role.name.lower().startswith(argument):
                    return role
        if result is None:
            raise commands.RoleNotFound(argument)
        if (result.position > ctx.author.top_role.position) and (
            ctx.author.guild.owner != ctx.author
        ):
            raise commands.BadArgument(
                f"You don't have permissions to touch {role.mention}"
            )
        return result


def can_execute_action(ctx, user, target) -> bool:
    return (
        user.id in ctx.bot.owner_ids
        or user == ctx.guild.owner
        or user.top_role > target.top_role
    )


class Banuser(commands.Converter):
    async def convert(self, ctx: commands.Context, argument):
        try:
            m = await utils.MemberConverter().convert(ctx, argument)
        except commands.MemberNotFound:
            try:
                member_id = int(argument, base=10)
            except ValueError:
                raise commands.BadArgument(
                    f"{argument} is not a valid member or member ID"
                ) from None
            else:
                m = ctx.guild.get_member(member_id)
                if m is None:
                    # just hackban everyone else tbh
                    return discord.Object(id=member_id)
        if not can_execute_action(ctx, ctx.author, m):
            raise commands.BadArgument(
                f"You can't execute this action on {m} due to role hiearchy"
            )
        return m


def can_execute_mute(
    ctx: commands.Context, user: discord.Member, target: discord.Member
):
    return (
        user.id in ctx.bot.owner_ids
        or user == ctx.guild.owner
        or user.top_role > target.top_role
        or ctx.bot != target
    )


orange = discord.Color.orange()
red = discord.Color.red()


class Moderation(commands.Cog):
    """Moderation commands"""

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(name="stafftools", id=314348604095594498)

    def __init__(self, bot: bot.AndreiBot) -> None:
        super().__init__()
        self.bot = bot

    @commands.has_permissions(administrator=True)
    async def logchannel(
        self,
        ctx: commands.Context[bot.AndreiBot],
        channel: typing.Optional[discord.TextChannel] = None,
    ):
        """Sets the log channel for this server.
        If no channel is given the bot stops logging"""

        em = discord.Embed(color=discord.Color.orange())
        if channel is None:
            await self.bot.pool.execute(
                "DELETE FROM log_channels WHERE guild_id=$1", ctx.guild.id
            )
            em.description = "Deleted log channel for this server"
        else:
            await self.bot.pool.execute(
                "INSERT INTO log_channels (server_id, channel_id) VALUES ($1, $2) ON CONFLICT (server_id) DO UPDATE SET channel_id=excluded.channel_id"
            )
            em.description = f"Set log channel to {channel.mention}"
        await ctx.send(embed=em)

    @commands.has_permissions(manage_messages=True)
    @commands.group(name="purge", aliases=["clear"], invoke_without_command=True)
    async def purge(
        self,
        ctx: commands.Context,
        user: typing.Optional[discord.User] = None,
        limit: typing.Optional[int] = 100,
        *,
        content=None,
    ):
        """Deletes messages from the current channel.
        `limit`: The number of messages to search through, defaults to 100.
        This is not the number of messages that will be deleted, though it can be.
        `content`: Deletes messages with that specific word/sentence.
        """
        if content is None:
            if user is None:

                def check(m):
                    return True

            else:

                def check(m):
                    return m.author == user

            mes = await ctx.channel.purge(
                limit=limit, before=ctx.message.created_at, check=check
            )
            em = discord.Embed(color=orange)
            em.set_author(name=ctx.author, icon_url=ctx.author.display_avatar)
            em.description = f"I deleted {len(mes)} messages"
            if user:
                em.description += f" from {user}"
        else:
            if user is None:

                def check(message: discord.Message):
                    if message.content == "":
                        return False
                    else:
                        return content.lower() in message.content.lower()

            else:

                def check(message: discord.Message):
                    if message.author != user:
                        return False
                    if message.content == "":
                        return False
                    else:
                        return content.lower() in message.content.lower()

            mes = await ctx.channel.purge(
                limit=limit, check=check, before=ctx.message.created_at
            )
            em = discord.Embed(color=orange)
            em.set_author(name=ctx.author, icon_url=ctx.author.display_avatar)
            em.description = (
                f'I deleted {len(mes)} messages with "{content.lower()}" in them'
            )
            if user:
                em.description += f" from {user}"
        await ctx.send(embed=em)
        with contextlib.suppress(discord.HTTPException):
            await ctx.message.delete()

    @commands.has_permissions(manage_messages=True)
    @purge.command(name="bot")
    async def _bot(self, ctx: commands.Context, limit: int = 100):
        """Deletes bot messages from the current channel.
        `limit`: The number of messages to search through, defaults to 100.
        This is not the number of messages that will be deleted, though it can be."""

        def check(m: discord.Message):
            return m.author.bot

        mes = await ctx.channel.purge(
            limit=limit, check=check, before=ctx.message.created_at
        )
        em = discord.Embed(color=orange)
        em.set_author(name=ctx.author, icon_url=ctx.author.display_avatar)
        em.description = f"I deleted {len(mes)} messages from bots"
        await ctx.send(embed=em)
        with contextlib.suppress(discord.HTTPException):
            await ctx.message.delete()

    @commands.has_permissions(manage_messages=True)
    @purge.command(aliases=["attachments", "files"])
    async def images(self, ctx: commands.Context, limit: int = 100):
        """Deletes messages with attachments from the current channel.
        `limit`: The number of messages to search through, defaults to 100.
        This is not the number of messages that will be deleted, though it can be."""

        def check(m: discord.Message):
            return bool(m.attachments)

        mes = await ctx.channel.purge(
            limit=limit, check=check, before=ctx.message.created_at
        )
        em = discord.Embed(color=orange)
        em.set_author(name=ctx.author, icon_url=ctx.author.display_avatar)
        em.description = f"I deleted {len(mes)} messages with attachments"
        await ctx.send(embed=em)
        with contextlib.suppress(discord.HTTPException):
            await ctx.message.delete()

    @commands.has_permissions(manage_messages=True)
    @purge.command(aliases=["sticker"])
    async def stickers(self, ctx: commands.Context, limit: int = 100):
        """Deletes mesages with stickers from the current channel.
        `limit`: The number of messages to search through, defaults to 100.
        This is not the number of messages that will be deleted, though it can be."""

        def check(m: discord.Message):
            return bool(m.stickers)

        mes = await ctx.channel.purge(
            limit=limit, check=check, before=ctx.message.created_at
        )
        em = discord.Embed(color=orange)
        em.set_author(name=ctx.author, icon_url=ctx.author.display_avatar)
        em.description = f"I deleted {len(mes)} messages with stickers"
        await ctx.send(embed=em)
        with contextlib.suppress(discord.HTTPException):
            await ctx.message.delete()

    @purge.command(aliases=["author"])
    async def self(self, ctx: commands.Context, limit: int = 100):
        """Deletes your own messages from the current channel.
        Anyone can call this command on themselves.
        `limit`: The number of messages to search through, defaults to 100.
        This is not the number of messages that will be deleted, though it can be."""

        def check(m: discord.Message):
            return m.author == ctx.author

        mes = await ctx.channel.purge(
            limit=limit, check=check, before=ctx.message.created_at
        )
        em = discord.Embed(color=orange)
        em.set_author(name=ctx.author, icon_url=ctx.author.display_avatar)
        em.description = f"I deleted {len(mes)} messages from {ctx.author.mention}"
        await ctx.send(embed=em)
        with contextlib.suppress(discord.HTTPException):
            await ctx.message.delete()

    @commands.has_guild_permissions(manage_messages=True)
    @commands.command(aliases=["cf"])
    async def clearfiles(self, ctx: commands.Context):
        """Deletes all deleted messages from this server saved in ram"""
        resp = await self.bot.pool.fetch(
            f"SELECT message_id FROM deleted_messages WHERE server_id = {ctx.guild.id}"
        )
        if not resp:
            return await ctx.send("There's nothing to delete")
        messages = [k["message_id"] for k in resp]
        for message in messages:
            self.bot.deleted_files.pop(message, None)
        await ctx.send("I deleted all files for this server")

    @commands.command(aliases=["timeout"])
    @commands.has_guild_permissions(moderate_members=True)
    async def mute(
        self,
        ctx: commands.Context,
        members: commands.Greedy[
            typing.Union[utils.MemberConverter, utils.RoleConverter]
        ],
        amount: commands.Greedy[utils.TimeConverter] = None,
        *,
        reason: Optional[str] = None,
    ):
        """gives `members` a timeout.
        members can take both server members or roles.
        amount defaults to 5 minutes.
        because of the crazy command syntax, here are some examples:
        .mute @user
        .mute @user1 @user2 @user3 1h
        .mute @user spamming
        .mute @user1 @user2 @role1 @user3 5h too active (notice the `@role`)"""

        if amount is None:
            amount = 300
        else:
            amount = int(sum(amount))

        if ref := await utils.get_member_reference(ctx.message):
            members.append(ref)

        if len(members) == 0:
            return await ctx.send(
                embed=discord.Embed(
                    color=red, description="`members` is a required argument"
                )
            )
        if amount > 2419199:
            amount = 2419200
        delta = datetime.timedelta(seconds=int(amount))
        s = humanfriendly.format_timespan(delta)

        tomute = []
        for entry in members:
            if isinstance(entry, discord.Member):
                if can_execute_action(ctx, ctx.author, entry):
                    if entry not in tomute:
                        tomute.append(entry)
            elif isinstance(entry, discord.Role):
                for member_role in entry.members:
                    if can_execute_action(ctx, ctx.author, member_role):
                        if member_role not in tomute:
                            tomute.append(member_role)
            else:
                return await ctx.send(
                    "I genuinely have no idea what happened, dm andrei with error code HARRYGAY"
                )
        em = discord.Embed(color=orange)
        if not tomute:
            return await ctx.send("You can't mute any of those members")
        failed = 0
        muted = []
        for member in tomute:
            try:
                await member.timeout(
                    (discord.utils.utcnow() + delta),
                    reason=reason
                    or f"action done by {ctx.author} (ID: {ctx.author.id})",
                )
                muted.append(member)
            except discord.Forbidden:
                failed += 1
        if len(muted) == 0:
            return await ctx.send("I can't mute any of  those members")
        em.description = f"{', '.join([m.mention for m in muted])} {'have' if len(muted) > 1 else 'has'} been muted for {s}"
        if reason:
            em.description += f"\nreason: {reason}"
        if failed:
            em.description += (
                f"\nfailed to mute: {failed} member{'s' if failed > 1 else ''}"
            )
        em.set_footer(icon_url=ctx.author.display_avatar, text=f"by {ctx.author}")
        await ctx.send(embed=em)

    @commands.command()
    @commands.has_guild_permissions(moderate_members=True)
    async def unmute(
        self, ctx: commands.Context, members: commands.Greedy[utils.MemberConverter]
    ):
        """Removes the timeout from `member`"""

        if ref := await utils.get_member_reference(ctx.message):
            members.append(ref)

        if len(members) == 0:
            return await ctx.send(
                embed=discord.Embed(
                    color=red, description="`members` is a required argument"
                )
            )
        to_unmute: list[discord.Member] = []

        for member in members:
            if member.timed_out_until is None:
                continue
            if can_execute_action(ctx, ctx.author, member):
                to_unmute.append(member)

        if not to_unmute:
            return await ctx.send("You can't unmute any of those members")

        unmuted = []
        failed = 0
        for member in to_unmute:
            try:
                await member.edit(
                    timed_out_until=None,
                    reason=f"action done by {ctx.author} (ID: {ctx.author.id})",
                )
                unmuted.append(member)
            except discord.Forbidden:
                failed += 1

        if (not unmuted) and (not failed):
            return await ctx.send("Something went wrong")

        em = discord.Embed(color=orange)
        em.description = f"{', '.join([str(m) for m in unmuted])} {'have' if len(unmuted)>1 else 'has'} been unmuted"
        if failed:
            em.description += (
                f"\nfailed to unmute: {failed} member{'s' if failed > 1 else ''}"
            )
        await ctx.send(embed=em)

    @commands.command()
    @commands.has_guild_permissions(ban_members=True)
    async def unban(
        self, ctx: commands.Context, user: discord.User, reason: str = None
    ):
        """Unbans a user from this server"""
        if reason is None:
            reason = f"Done by {ctx.author} (ID: {ctx.author.id})"
        else:
            reason += f"Done by {ctx.author} (ID: {ctx.author.id})"
        try:
            banentry = await ctx.guild.fetch_ban(discord.Object(id=int(user)))
        except discord.NotFound:
            raise commands.CommandInvokeError(f"{user} is not banned")
        try:
            await ctx.guild.unban(banentry.user, reason=reason)
        except discord.NotFound:
            raise commands.CommandInvokeError(f"{user} is not banned")
        await ctx.send(f"unbanned {banentry.user} (ID: {banentry.user.id})")

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(
        self, ctx: commands.Context, members: commands.Greedy[Banuser], *, reason=None
    ):
        """Allows you to ban multiple discord users.
        If more than one member is passed, converting errors will silently be ignored.
        """
        if reason is None:
            reason = f"Done by {ctx.author} (ID: {ctx.author.id})"

        if ref := await utils.get_reference(ctx.message):
            members.append(ref)

        members = await sanitize_targets(ctx, members)
        if len(members) == 0:
            raise commands.BadArgument("Missing members to ban")
        elif len(members) > 1:
            view = utils.ConfirmationView(ctx=ctx)
            view.message = await ctx.send(
                f"This will ban {len(members)} members, are you sure?", view=view
            )
            await view.wait()
            if view.value:
                failed = 0
                for member in members:

                    try:
                        await ctx.guild.ban(member, reason=reason)
                    except discord.HTTPException:
                        failed += 1
                em = discord.Embed(
                    color=orange, description=f"Banned {len(members)-failed} members"
                )
                em.set_author(name=ctx.author, icon_url=ctx.author.display_avatar)
                return await ctx.send(embed=em)

        else:
            member = members[0]
            if isinstance(member, discord.Object):
                try:
                    member = await self.bot.fetch_user(member.id)
                except discord.NotFound:
                    pass
            await ctx.guild.ban(member, reason=reason)
            em = discord.Embed(color=orange, description=f"Banned {member}")
            em.set_author(name=ctx.author, icon_url=ctx.author.display_avatar)
            await ctx.send(embed=em)

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def softban(
        self, ctx: commands.Context, members: commands.Greedy[Banuser], *, reason=None
    ):
        """Allows you to softban (ban and unban with 7 days message delete) multiple discord users.
        If more than one member is passed, converting errors will silently be ignored.
        """

        if ref := await utils.get_member_reference(ctx.message):
            members.append(ref)

        if reason is None:
            reason = f"Done by {ctx.author} (ID: {ctx.author.id})"
        members = await sanitize_targets(ctx, members)
        if len(members) == 0:
            raise commands.BadArgument("Missing members to softban")
        elif len(members) > 1:
            view = utils.ConfirmationView(ctx=ctx)
            view.message = await ctx.send(
                f"This will softban {len(members)} members, are you sure?", view=view
            )
            await view.wait()
            if view.value:
                failed = 0
                for member in members:

                    try:
                        await ctx.guild.ban(
                            member, reason=reason, delete_message_days=7
                        )
                        await ctx.guild.unban(member, reason=reason)
                    except discord.HTTPException:
                        failed += 1
                em = discord.Embed(
                    color=orange,
                    description=f"Softbannned {len(members)-failed} members",
                )
                em.set_author(name=ctx.author, icon_url=ctx.author.display_avatar)
                return await ctx.send(embed=em)

        else:
            member = members[0]
            if isinstance(member, discord.Object):
                try:
                    member = await self.bot.fetch_user(member.id)
                except discord.NotFound:
                    pass
            await ctx.guild.ban(member, reason=reason, delete_message_days=7)
            await ctx.guild.unban(member, reason=reason)
            em = discord.Embed(color=orange, description=f"Softbannned {member}")
            em.set_author(name=ctx.author, icon_url=ctx.author.display_avatar)
            await ctx.send(embed=em)

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(
        self, ctx: commands.Context, members: commands.Greedy[Banuser], *, reason=None
    ):
        """Allows you to kick multiple members.
        If more than one member is passed, converting errors will silently be ignored.
        """
        if reason is None:
            reason = f"Done by {ctx.author} (ID: {ctx.author.id})"
        members = await sanitize_targets(ctx, members)
        if len(members) == 0:
            raise commands.BadArgument("Missing members to kick")
        elif len(members) > 1:
            view = utils.ConfirmationView(ctx=ctx)
            view.message = await ctx.send(
                f"This will kick {len(members)} members, are you sure?", view=view
            )
            await view.wait()
            if view.value:
                failed = 0
                for member in members:
                    try:
                        await ctx.guild.kick(member, reason=reason)
                    except discord.HTTPException:
                        failed += 1
                em = discord.Embed(
                    color=orange, description=f"Kicked {len(members)-failed} members"
                )
                em.set_author(name=ctx.author, icon_url=ctx.author.display_avatar)
                return await ctx.send(embed=em)
        else:
            member = members[0]
            await ctx.guild.kick(member, reason=reason)
            em = discord.Embed(color=orange, description=f"Kicked {member}")
            em.set_author(name=ctx.author, icon_url=ctx.author.display_avatar)
            await ctx.send(embed=em)

    @commands.has_guild_permissions(manage_roles=True)
    @commands.group(invoke_without_command=True)
    async def role(self, ctx: commands.Context):
        """Add/remove roles from a member"""
        await ctx.send_help("role")

    @role.command()
    async def add(
        self,
        ctx: commands.Context,
        member: typing.Optional[utils.MemberConverter],
        roles: commands.Greedy[utils.RoleConverter],
    ):
        """Adds `roles` to `member`.
        Member can be the command invoker."""
        if member is None:
            if ctx.message.reference:
                member = await utils.get_member_reference(ctx.message)
            if member is None:
                member = ctx.author

        done = []
        failed = []
        if len(roles) == 0:
            em = discord.Embed(color=red, description="Missing roles to add")
            return await ctx.send(embed=em)
        elif len(roles) == 1:
            await member.add_roles(
                roles[0],
                reason=f"Command invoked by {ctx.author} (ID: {ctx.author.id})",
            )
            return await ctx.message.add_reaction("\U0001f44d")
        for role in roles:
            try:
                await member.add_roles(
                    role,
                    reason=f"Command invoked by {ctx.author} (ID: {ctx.author.id})",
                )
                done.append(role)
            except discord.Forbidden:
                failed.append(role)
        em = discord.Embed(color=orange)
        em.description = f"Added {len(done)} roles to {member}"
        if failed:
            em.add_field(
                name="Failed to add these roles",
                value=f"{' '.join([r.mention for r in failed])}\nDue to permissions/hierarchy",
            )
        await ctx.send(embed=em)

    @role.command()
    async def remove(
        self,
        ctx: commands.Context,
        member: typing.Optional[utils.MemberConverter],
        roles: commands.Greedy[utils.RoleConverter],
    ):
        """Removes `roles` from `memebr`.
        Member can be the command invoker."""
        if member is None:
            if ctx.message.reference:
                member = await utils.get_member_reference(ctx.message)
            if member is None:
                member = ctx.author
        toremove = []
        for role in roles:
            for authorrole in member.roles:
                if role.id == authorrole.id:
                    toremove.append(role)
        done = []
        failed = []
        if len(roles) == 0:
            em = discord.Embed(color=red, description="Missing roles to remove")
            return await ctx.send(embed=em)
        elif len(toremove) == 0:
            em = discord.Embed(
                color=red, description=f"{member} doesn't have any of those roles"
            )
            return await ctx.send(embed=em)
        elif len(toremove) == 1:
            await member.remove_roles(
                toremove[0],
                reason=f"Command invoked by {ctx.author} (ID: {ctx.author.id})",
            )
            return await ctx.message.add_reaction("\U0001f44d")
        for role in toremove:
            try:
                await member.remove_roles(
                    role,
                    reason=f"Command invoked by {ctx.author} (ID: {ctx.author.id})",
                )
                done.append(role)
            except discord.Forbidden:
                failed.append(role)
        em = discord.Embed(color=orange)
        em.description = f"Removed {len(done)} roles from {member}"
        if failed:
            em.add_field(
                name="Failed to remove these roles",
                value=f"{' '.join([r.mention for r in failed])}\nDue to permissions/hierarchy",
            )
        await ctx.send(embed=em)

    @commands.hybrid_command()
    async def muted(self, ctx: commands.Context):
        "Shows timed out members in this server"
        muted = []
        for member in ctx.guild.members:
            if member.is_timed_out():
                muted.append(member)
        if not muted:
            return await ctx.send("No members are muted", ephemeral=True)
        page = utils.MutedPages(muted, ctx=ctx)
        await page.start()


async def setup(bot: bot.AndreiBot):
    await bot.add_cog(Moderation(bot))
