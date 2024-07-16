import datetime
import typing
import discord
from discord.ext import commands
import bot

SQUARE_TICKS = {
    True: "\U00002705",
    False: "\U0000274c",
    None: "\U000025fb",
}


class Logs(commands.Cog):
    def __init__(self, bot: bot.AndreiBot) -> None:
        super().__init__()
        self.bot = bot
        self._channels = {}

    async def get_action(
        self,
        guild: discord.Guild,
        action_type: discord.AuditLogAction,
        target_id: int = None,
    ) -> discord.AuditLogEntry:
        if target_id:
            entries = [
                entry
                async for entry in guild.audit_logs(action=action_type)
                if (entry.created_at > self.allowed_time)
                and (entry.target.id == target_id)
            ]
        else:
            entries = [
                entry
                async for entry in guild.audit_logs(action=action_type)
                if (entry.created_at > self.allowed_time)
            ]
        if entries:
            return entries[0]
        return None

    async def cog_load(self) -> None:
        channels = await self.bot.pool.fetch("SELECT * FROM log_channels")
        for row in channels:
            self._channels[row["server_id"]] = row["channel_id"]

    @property
    def allowed_time(self) -> datetime.datetime:
        return discord.utils.utcnow() - datetime.timedelta(seconds=10)

    def get_channel(self, guild: discord.Guild) -> discord.TextChannel:
        channel_id = self._channels.get(guild.id)
        if channel_id is None:
            return
        return guild.get_channel(channel_id)

    @commands.Cog.listener(name="on_guild_role_create")
    async def on_role_create(self, role: discord.Role):
        log_channel = self.get_channel(role.guild)
        if log_channel is None:
            return
        embed = discord.Embed(color=discord.Color.green(), title="Role created")
        embed.description = role.mention
        embed.set_footer(text=f"role ID {role.id}")
        action = await self.get_action(
            role.guild, discord.AuditLogAction.role_create, role.id
        )
        if action:
            embed.set_author(name=action.user, icon_url=action.user.display_avatar)
        await log_channel.send(embed=embed)

    @commands.Cog.listener(name="on_guild_role_delete")
    async def on_guild_role_delete(self, role: discord.Role):
        log_channel = self.get_channel(role.guild)
        if log_channel is None:
            return
        embed = discord.Embed(color=discord.Color.red(), title="Role deleted")
        embed.description = f"name: `{role.name}`\ncolor: {hex(role.color.value) if role.color.value else 'default'}\nmembers: {len(role.members)}\npermission value [{role.permissions.value}](https://discordapi.com/permissions.html#{role.permissions.value})"
        embed.set_footer(text=f"role ID {role.id}")
        action = await self.get_action(
            role.guild, discord.AuditLogAction.role_delete, role.id
        )
        if action:
            embed.set_author(name=action.user, icon_url=action.user.display_avatar)
        await log_channel.send(embed=embed)

    @commands.Cog.listener(name="on_guild_role_update")
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        log_channel = self.get_channel(after.guild)
        if log_channel is None:
            return
        if before.members != after.members:
            return  # handled somewhere else
        embed = discord.Embed(
            color=discord.Color.orange(), description=f"`{after.name}`\n{after.mention}"
        )
        embed.title = "Role edited"
        action = await self.get_action(
            before.guild, discord.AuditLogAction.role_update, before.id
        )
        if action:
            embed.set_author(name=action.user, icon_url=action.user.display_avatar)
        embed.set_footer(text=f"Role ID: {before.id}")
        if before.name != after.name:
            embed.add_field(name="Name", value=f"{before.name} -> {after.name}")
        if before.color != after.color:
            embed.add_field(name="Color", value=f"{before.color} -> {after.color}")
        if before.mentionable != after.mentionable:
            embed.add_field(
                name="Mentionable", value=f"{before.mentionable} -> {after.mentionable}"
            )
        if before.hoist != after.hoist:
            embed.add_field(name="Hoisted", value=f"{before.hoist} -> {after.hoist}")
        if before.icon != after.icon:
            _before = None if before.icon is None else f"[before]({before.icon})"
            _after = None if after.icon is None else f"[after]({after.icon})"
            embed.add_field(name="Icon", value=f"{_before} -> {_after}")
        if before.unicode_emoji != after.unicode_emoji:
            embed.add_field(
                name="Emoji", value=f"{before.unicode_emoji} -> {after.unicode_emoji}"
            )
        if before.permissions != after.permissions:
            before_perms = f"[before](https://discordapi.com/permissions.html#{before.permissions.value})"
            after_perms = f"[after](https://discordapi.com/permissions.html#{after.permissions.value})"
            embed.add_field(
                name="Permissions", value=f"{before_perms} -> {after_perms}"
            )
        if before.position != after.position and not embed.fields:
            return  # we don't care about positions change
        await log_channel.send(embed=embed)

    @commands.Cog.listener(name="on_member_update")
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        log_channel = self.get_channel(after.guild)
        if log_channel is None:
            return
        roles_added = [r for r in after.roles if r not in before.roles]
        roles_removed = [r for r in before.roles if r not in after.roles]

        to_send = []

        if roles_added:
            embed = discord.Embed(color=discord.Color.green(), title="Roles added")
            embed.set_author(name=before, icon_url=before.display_avatar)
            embed.description = "\n".join([r.mention for r in roles_added])
            action = await self.get_action(
                before.guild, discord.AuditLogAction.member_role_update, before.id
            )
            if action:
                embed.set_footer(
                    icon_url=action.user.display_avatar,
                    text=f"by {action.user} (ID: {action.user.id})",
                )
            to_send.append(embed)

        if roles_removed:
            embed = discord.Embed(color=discord.Color.red(), title="Roles removed")
            embed.set_author(name=before, icon_url=before.display_avatar)
            embed.description = "\n".join([r.mention for r in roles_removed])
            action = await self.get_action(
                before.guild, discord.AuditLogAction.member_role_update, before.id
            )
            if action:
                embed.set_footer(
                    icon_url=action.user.display_avatar,
                    text=f"by {action.user} (ID: {action.user.id})",
                )
            to_send.append(embed)

        elif before.nick != after.nick:
            embed = discord.Embed(
                color=discord.Color.orange(), title="Nickname updated"
            )
            embed.set_author(name=before, icon_url=before.display_avatar)
            action = await self.get_action(
                before.guild, discord.AuditLogAction.member_update, before.id
            )
            if action:
                embed.set_footer(
                    icon_url=action.user.display_avatar,
                    text=f"by {action.user} (ID: {action.user.id})",
                )
            embed.add_field(name="before", value=before.nick)
            embed.add_field(name="after", value=after.nick)
            to_send.append(embed)
        elif (before.timed_out_until is None) and after.timed_out_until:
            embed = discord.Embed(color=discord.Color.orange(), title="Timed out")
            embed.set_author(name=before, icon_url=before.display_avatar)
            action = await self.get_action(
                before.guild, discord.AuditLogAction.member_update, before.id
            )
            if action:
                embed.set_footer(
                    icon_url=action.user.display_avatar,
                    text=f"by {action.user} (ID: {action.user.id})",
                )
            embed.description = (
                f"Until {discord.utils.format_dt(after.timed_out_until)}"
            )
            to_send.append(embed)
        for chunk in discord.utils.as_chunks(to_send, max_size=10):
            await log_channel.send(embeds=chunk)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        log_channel = self.get_channel(channel.guild)
        if log_channel is None:
            return
        action = await self.get_action(
            channel.guild, discord.AuditLogAction.channel_delete, channel.id
        )
        embed = discord.Embed(title="Channel deleted", color=discord.Color.orange())
        if action:
            embed.set_author(name=action.user, icon_url=action.user.display_avatar)
            embed.set_footer(text=f"User ID: {action.user.id}")
        embed.description = f"Type: {channel.__class__.__name__}"
        embed.description += f"\nName: {channel.name}"
        embed.description += f"\nID: {channel.id}"
        embed.description += (
            f"\nCreated: {discord.utils.format_dt(channel.created_at,'R')}"
        )
        if channel.category_id:
            embed.description += f"\nCategory ID: {channel.category_id}"
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        log_channel = self.get_channel(channel.guild)
        if log_channel is None:
            return
        action = await self.get_action(
            channel.guild, discord.AuditLogAction.channel_create, channel.id
        )
        embed = discord.Embed(title="Channel created", color=discord.Color.orange())
        if action:
            embed.set_author(name=action.user, icon_url=action.user.display_avatar)
            embed.set_footer(text=f"User ID: {action.user.id}")
        embed.description = f"Type: {channel.__class__.__name__}"
        embed.description += f"\n{channel.mention}"
        embed.description += f"\nID: {channel.id}"
        if channel.category_id:
            embed.description += f"\nCategory ID: {channel.category_id}"
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """On member kick"""
        log_channel = self.get_channel(member.guild)
        if log_channel is None:
            return
        action = await self.get_action(
            member.guild, discord.AuditLogAction.kick, member.id
        )
        if not action:
            return
        embed = discord.Embed(color=discord.Color.orange(), title="Member kicked")
        embed.set_author(name=member, icon_url=member.display_avatar)
        embed.description = f"User ID: {member.id}\nReason: {action.reason}"
        embed.set_footer(
            text=f"By {action.user} (ID: {action.user.id})",
            icon_url=action.user.display_avatar,
        )
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        log_channel = self.get_channel(guild)
        if log_channel is None:
            return
        embed = discord.Embed(color=discord.Color.orange(), title="Member banned")
        embed.description = f"User ID: {user.id}"
        embed.set_author(name=user, icon_url=user.display_avatar)
        action = await self.get_action(guild, discord.AuditLogAction.ban, user.id)
        if action:
            embed.description = f"Reason: {action.reason}"
            embed.set_footer(
                text=f"By {action.user} (ID: {action.user.id})",
                icon_url=action.user.display_avatar,
            )
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        log_channel = self.get_channel(guild)
        if log_channel is None:
            return
        embed = discord.Embed(color=discord.Color.orange(), title="Member unbanned")
        embed.description = f"User ID: {user.id}"
        embed.set_author(name=user, icon_url=user.display_avatar)
        action = await self.get_action(guild, discord.AuditLogAction.kick, user.id)
        if action:
            embed.set_footer(
                text=f"By {action.user} (ID: {action.user.id})",
                icon_url=action.user.display_avatar,
            )
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_emojis_update(
        self,
        guild: discord.Guild,
        before: typing.Sequence[discord.Emoji],
        after: typing.Sequence[discord.Emoji],
    ):
        log_channel = self.get_channel(guild)
        if log_channel is None:
            return
        added = [e for e in after if e not in before]
        removed = [e for e in before if e not in after]

        to_send = []

        for emoji in added:
            embed = discord.Embed(color=discord.Color.orange())
            embed.title = "Emoji added"
            action_style = discord.AuditLogAction.emoji_create
            action = await self.get_action(guild, action_style, emoji.id)
            if action:
                embed.set_footer(
                    text=f"by {action.user} (ID: {action.user.id})",
                    icon_url=action.user.display_avatar,
                )
            embed.set_thumbnail(url=emoji.url)
            embed.description = f"`{emoji}`\nImage [URL]({emoji.url})"
            if not added:
                embed.description += (
                    f"\nEmoji added {discord.utils.format_dt(emoji.created_at, 'R')}"
                )
            to_send.append(embed)

        for emoji in removed:
            embed = discord.Embed(color=discord.Color.orange())
            embed.title = "Emoji removed"
            action_style = discord.AuditLogAction.emoji_delete
            action = await self.get_action(guild, action_style, emoji.id)
            if action:
                embed.set_footer(
                    text=f"by {action.user} (ID: {action.user.id})",
                    icon_url=action.user.display_avatar,
                )
            embed.set_thumbnail(url=emoji.url)
            embed.description = f"`{emoji}`\nImage [URL]({emoji.url})"
            if not added:
                embed.description += (
                    f"\nEmoji added {discord.utils.format_dt(emoji.created_at, 'R')}"
                )
            to_send.append(embed)

        existant = set.union(set(after) - set(added), set(before) - set(removed))
        for emoji in existant:
            embed = discord.Embed(color=discord.Color.orange())
            before_emoji = discord.utils.get(before, id=emoji.id)
            after_emoji = emoji
            if before_emoji and after_emoji:
                if before_emoji.name == after_emoji.name:
                    continue

                action_style = discord.AuditLogAction.emoji_update
                action = await self.get_action(guild, action_style)
                if action is not None:
                    embed.set_footer(
                        text=f"by {action.user} (ID: {action.user.id})",
                        icon_url=action.user.display_avatar,
                    )
                embed.set_thumbnail(url=emoji.url)
                embed.title = "Emoji name updated"
                embed.description = f"`{emoji}`"
                embed.add_field(name="before", value=before_emoji.name)
                embed.add_field(name="after", value=after_emoji.name)

                to_send.append(embed)

        for chunk in discord.utils.as_chunks(to_send, max_size=10):
            await log_channel.send(embeds=chunk)

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel
    ):
        log_channel = self.get_channel(before.guild)
        if log_channel is None:
            return
        to_send = []
        embed = discord.Embed(color=discord.Color.orange(), title="Channel updated")
        embed.set_footer(text=f"Channel ID: {before.id}")
        embed.description = f"{after.mention}\nName: {after.name}\nCategory: {getattr(after.category, 'name', 'no category')}"
        action = await self.get_action(
            before.guild, discord.AuditLogAction.channel_update, before.id
        )
        if action:
            embed.set_author(name=action.user, icon_url=action.user.display_avatar)

        if before.name != after.name:
            embed.add_field(name="Name updated", value=f"{before.name} -> {after.name}")

        if (
            hasattr(before, "topic")
            and hasattr(after, "topic")
            and before.topic != after.topic
        ):
            embed.add_field(
                name="Topic updated",
                value=f"before:\n{discord.utils.remove_markdown(str(before.topic))}\nafter:\n{discord.utils.remove_markdown(str(after.topic))}",
            )

        if (before_cat := getattr(before.category, "name", "no category")) != (
            after_cat := getattr(after.category, "name", "no category")
        ):
            embed.add_field(name="Category", value=f"{before_cat} -> {after_cat}")
        if embed.fields:
            to_send.append(embed)

        if before.overwrites != after.overwrites:
            targets = set.union(
                set(before.overwrites.keys()), set(after.overwrites.keys())
            )
            for target in targets:
                updated_perms = []
                b_o = dict(before.overwrites_for(target))
                a_o = dict(after.overwrites_for(target))
                for perm, value in b_o.items():
                    if value != a_o[perm]:
                        updated_perms.append(
                            f"{str(perm).replace('server', 'guild').replace('_', ' ').title()}: {SQUARE_TICKS[value]} -> {SQUARE_TICKS[a_o[perm]]}"
                        )
                if updated_perms:
                    perm_emb = discord.Embed(
                        colour=discord.Colour.orange(),
                        description="{}\n{}".format(
                            after.mention, "\n".join(updated_perms)
                        ),
                    )
                    _actions = [
                        discord.AuditLogAction.overwrite_create,
                        discord.AuditLogAction.overwrite_delete,
                        discord.AuditLogAction.overwrite_update,
                    ]
                    for _action in _actions:
                        __action = await self.get_action(
                            before.guild, _action, before.id
                        )
                        if __action is not None:
                            action = __action
                            break

                    if isinstance(target, discord.Member):
                        perm_emb.title = "Permissions for member updated"
                        perm_emb.set_author(name=target, icon_url=target.display_avatar)
                    elif isinstance(target, discord.Role):
                        perm_emb.title = "Permissions for role updated"
                        perm_emb.set_author(name=target)
                    else:
                        perm_emb.title = "Permissions updated"
                    if action is not None:
                        perm_emb.set_footer(
                            text=f"by {action.user} (ID: {action.user.id})",
                            icon_url=action.user.display_avatar,
                        )
                    else:
                        perm_emb.set_footer(
                            text=f"Target ID: {target.id}\nChannel ID: {after.id}"
                        )
                    to_send.append(perm_emb)
        for chunk in discord.utils.as_chunks(to_send, max_size=10):
            await log_channel.send(embeds=chunk)

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        log_channel = self.get_channel(after)
        if log_channel is None:
            return
        embed = discord.Embed(color=discord.Color.orange(), title="Server updated")
        action = await self.get_action(after, discord.AuditLogAction.guild_update)
        if action is not None:
            embed.set_author(name=action.user, icon_url=action.user.display_avatar)
            embed.set_footer(text=f"Author ID: {action.user.id}")
        if before.afk_channel != after.afk_channel:
            embed.add_field(
                name="Afk channel",
                value=f"{before.afk_channel.mention if before.afk_channel else None} -> {after.afk_channel.mention if after.afk_channel else None}",
            )
        if before.system_channel != after.system_channel:
            embed.add_field(
                name="System channel",
                value=f"{before.system_channel.mention if before.system_channel else None} -> {after.system_channel.mention if after.system_channel else None}",
            )
        if before.owner != after.owner:
            embed.add_field(name="Ownership", value=f"{before.owner} -> {after.owner}")
        if before.name != after.name:
            embed.add_field(name="Name", value=f"{before.name} -> {after.name}")
        if before.banner != after.banner:
            before_url = f"[before]({before.banner.url})" if before.banner else None
            after_url = f"[after]({after.banner.url})" if after.banner else None
            embed.add_field(
                name="Banner",
                value=f"{before_url} -> {after_url}",
            )
        if before.icon != after.icon:
            before_url = f"[before]({before.icon.url})" if before.icon else None
            after_url = f"[after]({after.icon.url})" if after.icon else None
            embed.add_field(
                name="Icon",
                value=f"{before_url} -> {after_url}",
            )
        if not embed.fields:
            return
        await log_channel.send(embed=embed)

    @commands.Cog.listener("on_guild_stickers_update")
    async def logger_on_guild_stickers_update(
        self,
        guild: discord.Guild,
        before: typing.Sequence[discord.Sticker],
        after: typing.Sequence[discord.Sticker],
    ):
        log_channel = self.get_channel(guild)
        if log_channel is None:
            return
        added = [s for s in after if s not in before]
        removed = [s for s in before if s not in after]

        to_send = []
        if added:
            for sticker in added:
                em = discord.Embed(color=discord.Color.green(), title="Sticker created")
                em.set_author(name=sticker.name)
                action = await self.get_action(
                    guild, discord.AuditLogAction.sticker_create, sticker.id
                )
                if action:
                    em.set_footer(
                        text=f"by {action.user} (ID: {action.user.id})",
                        icon_url=action.user.display_avatar,
                    )
                em.description = sticker.description
                em.set_image(url=sticker.url)
                to_send.append(em)

        if removed:
            for sticker in added:
                em = discord.Embed(color=discord.Color.red(), title="Sticker deleted")
                em.set_author(name=sticker.name)
                action = await self.get_action(
                    guild, discord.AuditLogAction.sticker_delete, sticker.id
                )
                if action:
                    em.set_footer(
                        text=f"by {action.user} (ID: {action.user.id})",
                        icon_url=action.user.display_avatar,
                    )
                em.description = sticker.description
                em.set_image(url=sticker.url)
                to_send.append(em)

        existant = set.union(set(after) - set(added), set(before) - set(removed))
        for sticker in existant:
            action_type = discord.AuditLogAction.sticker_update
            before_sticker = discord.utils.get(before, id=sticker.id)
            after_sticker = sticker
            if before_sticker and after_sticker:
                if (
                    before_sticker.description == after_sticker.description
                    and before_sticker.name == after_sticker.name
                ):
                    continue
                new_embed = discord.Embed(
                    title="Sticker Updated", colour=discord.Colour.orange()
                )
                new_embed.set_author(name=after_sticker.name)
                new_embed.set_thumbnail(url=after_sticker.url)
                action = await self.get_action(guild, action_type, before_sticker.id)
                if action:
                    new_embed.set_footer(
                        text=f"by {action.user} (ID: {action.user.id})",
                        icon_url=action.user.display_avatar,
                    )
                if before_sticker.name != after_sticker.name:
                    new_embed.add_field(
                        name="Name",
                        value=f"{before_sticker.name} -> {after_sticker.name}",
                    )
                if before_sticker.description != after_sticker.description:
                    new_embed.add_field(
                        name="Description",
                        inline=False,
                        value=f"before:\n{before_sticker.description}\n\nafter:\n{after_sticker.description}",
                    )
                if not new_embed.fields:
                    continue
                to_send.append(new_embed)

        for chunk in discord.utils.as_chunks(to_send, max_size=10):
            await log_channel.send(embeds=chunk)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        log_channel = self.get_channel(member.guild)
        if log_channel is None:
            return
        to_send = []
        if (before.channel is None) and after.channel is not None:
            embed = discord.Embed(color=discord.Color.green())
            embed.title = "Joined voice channel"
            embed.description = f"User ID: {member.id}\n{after.channel.mention}"
            embed.set_author(name=member, icon_url=member.display_avatar)
            to_send.append(embed)
        elif (
            (before.channel is not None)
            and (after.channel is not None)
            and before.channel != after.channel
        ):
            embed = discord.Embed(color=discord.Color.orange())
            action = await self.get_action(
                member.guild, discord.AuditLogAction.member_move
            )
            if action:
                embed.set_footer(
                    text=f"by {action.user} (ID: {action.user.id})",
                    icon_url=action.user.display_avatar,
                )
            embed.set_author(name=member, icon_url=member.display_avatar)
            embed.title = "Changed voice channel"
            embed.description = f"{before.channel.mention} -> {after.channel.mention}"
            to_send.append(embed)
        elif (before.channel is not None) and after.channel is None:
            embed = discord.Embed(color=discord.Color.red())
            embed.set_author(name=member, icon_url=member.display_avatar)
            action = await self.get_action(
                member.guild, discord.AuditLogAction.member_disconnect
            )
            if action:
                embed.set_footer(
                    text=f"by {action.user} (ID: {action.user.id})",
                    icon_url=action.user.display_avatar,
                )
            embed.description = (
                f"user ID: {member.id}\nDisconnected from {before.channel.mention}"
            )
            to_send.append(embed)
        else:

            em_ = discord.Embed(color=discord.Color.orange())
            em_.set_author(name=member, icon_url=member.display_avatar)
            em_.description = f"Member ID: {member.id}\nin {after.channel.mention}"
            if before.self_deaf != after.self_deaf:
                em_.add_field(
                    name="Self deaf",
                    value=f"{SQUARE_TICKS[before.self_deaf]} -> {SQUARE_TICKS[after.self_deaf]}",
                )
            if before.self_mute != after.self_mute:
                em_.add_field(
                    name="Self mute",
                    value=f"{SQUARE_TICKS[before.self_mute]} -> {SQUARE_TICKS[after.self_mute]}",
                )
            if before.self_video != after.self_video:
                _type = "Esexing" if len(after.channel.members) == 2 else "Videocalling"
                em_.add_field(
                    name=_type,
                    value=f"{SQUARE_TICKS[before.self_video]} -> {SQUARE_TICKS[after.self_video]}",
                )
            if before.self_stream != after.self_stream:
                em_.add_field(
                    name="Streaming",
                    value=f"{SQUARE_TICKS[before.self_stream]} -> {SQUARE_TICKS[after.self_stream]}",
                )
            if before.deaf != after.deaf:
                action = await self.get_action(
                    member.guild, discord.AuditLogAction.member_update, member.id
                )
                if action:
                    em_.set_footer(
                        text=f"by {action.user} (ID: {action.user.id})",
                        icon_url=action.user.display_avatar,
                    )
                em_.add_field(
                    name="Server deaf",
                    value=f"{SQUARE_TICKS[before.deaf]} -> {SQUARE_TICKS[after.deaf]}",
                )
            if before.mute != after.mute:
                action = await self.get_action(
                    member.guild, discord.AuditLogAction.member_update, member.id
                )
                if action:
                    em_.set_footer(
                        text=f"by {action.user} (ID: {action.user.id})",
                        icon_url=action.user.display_avatar,
                    )
                em_.add_field(
                    name="Server mute",
                    value=f"{SQUARE_TICKS[before.mute]} -> {SQUARE_TICKS[after.mute]}",
                )
            if em_.fields:
                to_send.append(em_)
        for chunk in discord.utils.as_chunks(to_send, max_size=10):
            await log_channel.send(embeds=chunk)


# message delete                 (raw event?)
# multiple message delete        (raw event?)


# remake setup log commands


async def setup(bot: bot.AndreiBot):
    await bot.add_cog(Logs(bot))
