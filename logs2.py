import datetime
import typing
import discord
from discord.ext import commands
import bot

SQUARE_TICKS = {
    True: "\U00002705",
    False: "\U0000274c",
    None: "\U000025fd",
}

# COMBINE JOIN-LEAVE LOGS
# better leave logs (check if kick/ban)
# message delete                 (raw event?)
# multiple message delete        (raw event?)
# same for message edit
# remake setup log commands and separate events to channels
# add log related commands HERE


class Logs2(commands.Cog):
    def __init__(self, bot: bot.AndreiBot) -> None:
        super().__init__()
        self.bot = bot
        self._channels = {}

    async def load_channels(self):

        data = await self.bot.pool.fetch("SELECT * FROM log_channels")
        for row in data:
            self._channels[row["server_id"]] = row["channel_id"]

    async def cog_load(self) -> None:
        await self.load_channels()

    def get_channel(self, guild: discord.Guild) -> discord.TextChannel:
        channel_id = self._channels.get(guild.id)
        if channel_id is None:
            return
        return guild.get_channel(channel_id)

    async def guild_update(self, action: discord.AuditLogEntry):
        target: discord.Guild = action.target
        action.category

    @commands.Cog.listener(name="on_audit_log_entry_create")
    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry):

        # get channel

        match entry.category:
            case discord.AuditLogActionCategory.create:
                color = discord.Color.green()
            case discord.AuditLogActionCategory.delete:
                color = discord.Color.red()
            case _:
                color = discord.Color.orange()
        em = discord.Embed(color=color)
        if entry.user:
            em.set_author(
                name=f"Done by: {entry.user} (ID: {entry.user.id})",
                icon_url=entry.user.display_avatar,
            )

        action = discord.AuditLogAction
        match entry.action:
            case action.guild_update:
                em.title = "Server updated"
                for (name, before), (_, after) in zip(
                    entry.changes.before, entry.changes.after
                ):
                    match name:
                        case "afk_channel" | "system_channel" | "public_updates_channel" | "rules_channel":
                            before = before.mention if before else "None"
                            after = after.mention if after else "None"
                            em.add_field(name=name.replace("_", " "), value=f"{before} -> {after}",)
                        case "afk_timeout":
                            em.add_field(
                                name="afk timeout seconds", value=f"{before} -> {after}"
                            )
                        case "default_notifications":
                            before = before.replace("_", " ")
                            after = after.replace("_", " ")
                            em.add_field(
                                name=name.replace("_", " "),
                                value=f"{before} -> {after}",
                            )
                        case "mfa_level":
                            em.add_field(
                                name=name.replace("_", " "),
                                value=f"{before.name} -> {after.name}",
                            )
                        case "name" | "owner" | "icon" | "banner" | "description" | "vanity_url_code":
                            em.add_field(name=name.replace("_", " "), value=f"{before} -> {after}")
                

            case action.channel_create:
                em.title = "Channel created"
            case action.channel_update:
                em.title = "Channel updated"
            case action.channel_delete:
                em.title = "Channel deleted"
            case action.overwrite_create:
                em.title = "Overwrite created"
            case action.overwrite_update:
                em.title = "Overwrite updated"
            case action.overwrite_delete:
                em.title = "Overwrite deleted"
            case action.kick:
                pass  # handle differently
            case action.member_prune:
                em.title = "Members pruned"
            case action.ban:
                pass  # handle differently
            case action.unban:
                em.title = "Member unbanned"
            case action.member_update:
                em.title = "Member updated"
            case action.member_role_update:
                em.title = "Member roles updated"
            case action.member_move:
                em.title = "Member moved"
            case action.member_disconnect:
                em.title = "Member diconnected"
            case action.bot_add:
                em.title = "Bot added"
            case action.role_create:
                em.title = "Role created"
            case action.role_update:
                em.title = "Role updated"
            case action.role_delete:
                em.title = "Role deleted"
            case action.invite_create:
                em.title = "Invite created"
            case action.invite_update:
                em.title = "Invite updated"
            case action.invite_delete:
                em.title = "Invite deleted"
            case action.webhook_create:
                em.title = "Webhook created"
            case action.webhook_update:
                em.title = "Webhook updated"
            case action.webhook_delete:
                em.title = "Webhook deleted"
            case action.emoji_create:
                em.title = "Emoji created"
            case action.emoji_update:
                em.title = "Emoji updated"
            case action.emoji_delete:
                em.title = "Emoji deleted"
            case action.message_delete:
                em.title = "Message deleted"
            case action.message_bulk_delete:
                em.title = "Bulk message delete"
                # make a file and send i think
            case action.message_pin:
                em.title = "Message pinned"
            case action.message_unpin:
                em.title = "Message unpinned"
            case action.integration_create:
                em.title = "Integration created"
            case action.integration_update:
                em.title = "Integration updated"
            case action.integration_delete:
                em.title = "Integration deleted"
            case action.stage_instance_create:
                em.title = "Stage created"
            case action.stage_instance_update:
                em.title = "Stage updated"
            case action.stage_instance_delete:
                em.title = "Stage deleted"
            case action.sticker_create:
                em.title = "Sticker created"
            case action.sticker_update:
                em.title = "Sticker updated"
            case action.sticker_delete:
                em.title = "Sticker deleted"
            case action.scheduled_event_create:
                em.title = "Event created"
            case action.scheduled_event_update:
                em.title = "Event updated"
            case action.scheduled_event_delete:
                em.title = "Event deleted"
            case action.thread_create:
                em.title = "Thread created"
            case action.thread_update:
                em.title = "Thread updated"
            case action.thread_delete:
                em.title = "Thread deleted"
            case action.app_command_permission_update:
                em.title = "App command permissions updated"
            case action.automod_rule_create:
                em.title = "Automod rule created"
            case action.automod_rule_update:
                em.title = "Automod rule updated"
            case action.automod_rule_delete:
                em.title = "Automod rule deleted"
            case action.automod_block_message:
                em.title = "Automod blocked message"
            case action.automod_flag_message:
                em.title = "Automod flagged message"
            case action.automod_timeout_member:
                em.title = "Automod timeout member"
            case action.creator_monetization_request_created:
                pass
            case action.creator_monetization_terms_accepted:
                pass
            case action.soundboard_sound_create:
                em.title = "Soundboard sound created"
            case action.soundboard_sound_update:
                em.title = "Soundboard sound updated"
            case action.soundboard_sound_delete:
                em.title = "Soundboard sound deleted"


async def setup(bot: bot.AndreiBot):
    await bot.add_cog(Logs2(bot))
