import datetime
import enum
import re
import traceback
import typing
import aiohttp
from discord.ext import commands, tasks
from discord import Forbidden, HTTPException, NotFound, app_commands
import discord
from discord.ext.commands.converter import GuildConverter, RoleConverter
import utils
import bot
from enum import Enum

url_rx = re.compile(
    r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
)


DatesStyles = [
    app_commands.Choice(name="Short Time", value="t"),
    app_commands.Choice(name="Long Time", value="T"),
    app_commands.Choice(name="Short Date", value="d"),
    app_commands.Choice(name="Short Date and Time", value="f"),
    app_commands.Choice(name="Long Date and Time", value="F"),
    app_commands.Choice(name="Relative Time", value="R"),
    app_commands.Choice(name="Timestamp", value="None"),
]


class months(enum.Enum):
    January = 1
    February = 2
    March = 3
    April = 4
    May = 5
    June = 6
    July = 7
    August = 8
    September = 9
    October = 10
    November = 11
    December = 12


#@app_commands.allowed_installs(guilds=True, users=True)
#@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)


class ProfileView(discord.ui.View):
    async def on_timeout(self) -> None:
        if self.message:
            await self.message.edit(view=None)


testguild_id = 831556458398089217
mushroom_id = 749670809110315019
allowed_guilds = (testguild_id, mushroom_id)
testguild = discord.Object(id=testguild_id)
mushroom = discord.Object(id=mushroom_id)


class purge(app_commands.Group):
    def __init__(self, bot: bot.AndreiBot):
        super().__init__(default_permissions=discord.Permissions(manage_roles=True))
        self.bot = bot

    @app_commands.command(name="message", description="Purges messages")
    @app_commands.describe(
        limit="The number of messages to search through, this is not the number of mssages that will be deleted, though it can be",
        content="Specific word/sentence to look for, deletes any message if not given",
    )
    async def purge_message(
        self, interaction: discord.Interaction, limit: int, content: str = None
    ):
        if not (
            interaction.channel.permissions_for(interaction.user).manage_messages
            or (interaction.user.id in self.bot.owner_ids)
        ):
            return await interaction.response.send_message(
                "You are missing the manage messages perms", ephemeral=True
            )
        await interaction.response.defer()
        if content:

            def mcheck(m: discord.Message):
                if m.content:
                    return content.lower() in m.content.lower()

            deleted = await interaction.channel.purge(
                limit=limit, check=mcheck, before=interaction.created_at
            )
            repl = f"with {content} in them"
        else:
            deleted = await interaction.channel.purge(
                limit=limit, before=interaction.created_at
            )
            repl = ""
        await interaction.followup.send(f"Deleted {len(deleted)} messages {repl}")

    @app_commands.command(
        name="files", description="Deletes messages with files or embeds"
    )
    @app_commands.describe(
        limit="The number of messages to search through, this is not the number of mssages that will be deleted, though it can be"
    )
    async def purge_files(self, interaction: discord.Interaction, limit: int):
        if not (
            interaction.channel.permissions_for(interaction.user).manage_messages
            or (interaction.user.id in self.bot.owner_ids)
        ):
            return await interaction.response.send_message(
                "You are missing the manage messages perms", ephemeral=True
            )
        await interaction.response.defer()
        deleted = await interaction.channel.purge(
            limit=limit,
            before=interaction.created_at,
            check=lambda m: m.attachments or m.embeds,
        )
        await interaction.followup.send(
            f"Deleted {len(deleted)} messages with files/embeds"
        )

    @app_commands.command(
        name="user", description="Deletes messages from a specific user"
    )
    @app_commands.describe(
        limit="The number of messages to search through, this is not the number of mssages that will be deleted, though it can be",
        user="The user to delete messages from",
    )
    async def purge_user(
        self, interaction: discord.Interaction, user: discord.User, limit: int
    ):
        if not (
            interaction.channel.permissions_for(interaction.user).manage_messages
            or (interaction.user.id in self.bot.owner_ids)
            or (interaction.user == user)
        ):
            return await interaction.response.send_message(
                "You are missing the manage messages perms", ephemeral=True
            )
        await interaction.response.defer()
        deleted = await interaction.channel.purge(
            limit=limit, before=interaction.created_at, check=lambda m: m.author == user
        )
        await interaction.followup.send(f"Deleted {len(deleted)} messages from {user}")

    @app_commands.command(name="bot", description="Deletes messages from bots")
    @app_commands.describe(
        limit="The number of messages to search through, this is not the number of mssages that will be deleted, though it can be"
    )
    async def purge_bot(self, interaction: discord.Interaction, limit: int):
        if not (
            interaction.channel.permissions_for(interaction.user).manage_messages
            or (interaction.user.id in self.bot.owner_ids)
        ):
            return await interaction.response.send_message(
                "You are missing the manage messages perms", ephemeral=True
            )
        await interaction.response.defer()
        deleted = await interaction.channel.purge(
            limit=limit, check=lambda m: m.author.bot, before=interaction.created_at
        )
        await interaction.followup.send(f"Deleted {len(deleted)} messages from bots")


class snipe(app_commands.Group):
    """Snipe related commands"""

    def __init__(self, bot: bot.AndreiBot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="deleted", description="Shows deleted messages")
    @app_commands.describe(
        offset="How far to search",
        hidden="Whether the message response should be ephemeral",
        user="The user to search for, if not given then the bot searches for deleted messages from all users",
    )
    async def _snipe(
        self,
        interaction: discord.Interaction,
        offset: int = None,
        user: discord.User = None,
        hidden: bool = False,
    ):
        if offset is not None:
            offset = offset - 1
        else:
            offset = 0
        if user is not None:
            request = f"SELECT * FROM deleted_messages WHERE channel_id = {interaction.channel.id} AND author_id = {user.id} ORDER BY datetime DESC LIMIT 1 OFFSET {offset}"
        else:
            request = f"SELECT * FROM deleted_messages WHERE channel_id = {interaction.channel.id} ORDER BY datetime DESC LIMIT 1 OFFSET {offset}"
        res = await self.bot.pool.fetchrow(request)
        if not res:
            return await interaction.response.send_message(
                "I couldn't find anything", ephemeral=hidden
            )
        data = res
        em = discord.Embed(color=discord.Color.orange())
        if data["reference_message_id"]:
            _message_id = data["reference_message_id"]
            _message = self.bot._connection._get_message(_message_id)
            if _message is None:
                try:
                    _message = await interaction.channel.fetch_message(_message_id)
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
        view = utils.InteractionDeletedView(
            bot=self.bot,
            author=m,
            interaction=interaction,
            hidden=hidden,
            message_id=data["message_id"],
        )
        await interaction.response.send_message(embed=em, view=view, ephemeral=hidden)
        view.message = await interaction.original_response()

    @app_commands.command(name="edits", description="Shows edited messages")
    @app_commands.describe(
        messages="How far to search",
        hidden="Whether the message response should be ephemeral",
        message_id="This can be any message ID, the messages parameter will be bypassed",
    )
    async def editsnipe(
        self,
        interaction: discord.Interaction,
        messages: int = None,
        hidden: bool = False,
        message_id: str = "",
    ):

        if message_id:
            mes_id = await self.bot.pool.fetchval(
                f"SELECT message_id FROM edited_messages WHERE message_id = {message_id}"
            )
            if not mes_id:
                return await interaction.response.send_message(
                    f"I couldn't find anything with ID: {message_id}", ephemeral=hidden
                )
            query = f"SELECT message_content, datetime, author_id FROM edited_messages WHERE message_id = {mes_id} ORDER BY datetime ASC"
        elif messages is None:  # search one only
            mes_id = await self.bot.pool.fetchval(
                f"SELECT message_id, datetime FROM edited_messages WHERE channel_id = {interaction.channel.id} ORDER BY datetime DESC LIMIT 1"
            )
            if not mes_id:
                return await interaction.response.send_message(
                    "I couldn't find anything", ephemeral=True
                )
            query = f"SELECT message_content, datetime, author_id FROM edited_messages WHERE message_id = {mes_id} ORDER BY datetime ASC"
        elif messages is not None:  # offset
            try:
                messages = int(messages) - 1
            except ValueError:
                return await interaction.response.send_message(
                    f"`{messages}` is an invalid number", ephemeral=True
                )
            mes_id = await self.bot.pool.fetchval(
                f"SELECT DISTINCT message_id, datetime FROM edited_messages WHERE channel_id = {interaction.channel.id} ORDER BY datetime DESC LIMIT 1 OFFSET {messages}"
            )
            if not mes_id:
                return await interaction.response.send_message(
                    "I couldn't find anything"
                )
            query = f"SELECT message_content, datetime, author_id FROM edited_messages WHERE message_id = {mes_id} ORDER BY datetime ASC"

        allmessages = await self.bot.pool.fetch(query)
        edits = allmessages[1:]
        # edits = [] #list of all edits [(content, timestamp, author), ...]
        original: tuple = allmessages[0]
        author = self.bot.get_user(int(original[-1]))
        if author is None:
            try:
                author = await self.bot.fetch_user(int(original[-1]))
            except (discord.NotFound, discord.HTTPException):
                author = None
        pages = utils.InteractionSnipeSimplePages(
            entries=edits,
            interaction=interaction,
            original=original,
            author=author,
            hidden=hidden,
        )
        await pages.start()


async def check_dms(user: discord.User):
    try:
        await user.send()
    except discord.HTTPException as e:
        if e.code == 50006:  # cannot send an empty message
            return True
        elif e.code == 50007:  # cannot send messages to this user
            return False
        else:
            raise


async def on_error(interaction: discord.Interaction, error):
    if interaction.user.id == bot.ANDREI_ID:
        error = getattr(error, "original", error)
        exc = getattr(error, "original", error)
        etype = type(exc)
        trace = exc.__traceback__
        lines = traceback.format_exception(etype, exc, trace)
        traceback_text = "".join(lines)

        if interaction.response.is_done():
            await interaction.followup.send(f"```{traceback_text}```")
        else:
            await interaction.response.send_message(f"```{traceback_text}```")
    else:
        if interaction.response.is_done():
            await interaction.followup.send(error)
        else:
            await interaction.response.send_message(error, ephemeral=True)


def can_add_role(author: discord.Member, target: discord.Member, role: discord.Role):
    if not role.is_assignable():
        return False
    if role.id in [r.id for r in target.roles]:
        return False
    if author.top_role.position <= role.position:
        return False
    return True


class role(app_commands.Group):
    """Role related commands"""

    def __init__(self, bot: bot.AndreiBot):
        self.bot = bot
        super().__init__(default_permissions=discord.Permissions(manage_roles=True))

    @app_commands.command(name="add", description="Add role(s) to a member")
    @app_commands.describe(
        member="The target member, uses the current user if not given",
        role="The role to add",
        role2="Another optional role to add",
        role3="Another optional role to add",
        role4="Another optional role to add",
        role5="Another optional role to add",
    )
    async def add_role(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role,
        role2: discord.Role = None,
        role3: discord.Role = None,
        role4: discord.Role = None,
        role5: discord.Role = None,
    ):
        if not interaction.user.guild_permissions.manage_roles:
            return await interaction.response.send_message(
                "You are missing the manage roles permission", ephemeral=True
            )
        to_add = []
        if role.id not in [r.id for r in member.roles]:
            to_add.append(role)
        if (
            (role2)
            and (role2 not in to_add)
            and (role2.id not in [r.id for r in member.roles])
        ):
            to_add.append(role2)
        if (
            (role3)
            and (role3 not in to_add)
            and (role3.id not in [r.id for r in member.roles])
        ):
            to_add.append(role3)
        if (
            (role4)
            and (role4 not in to_add)
            and (role4.id not in [r.id for r in member.roles])
        ):
            to_add.append(role4)
        if (
            (role5)
            and (role5 not in to_add)
            and (role5.id not in [r.id for r in member.roles])
        ):
            to_add.append(role5)

        if len(to_add) == 0:
            return await interaction.response.send_message(
                "No changes need to be made", ephemeral=True
            )

        failed = []
        newroles = []
        for role in to_add:
            if not can_add_role(interaction.user, member, role):
                failed.append(role)
            else:
                newroles.append(role)
        if len(newroles) == 0:
            return await interaction.response.send_message(
                "I can't add any of those roles due to permissions", ephemeral=True
            )
        await interaction.response.defer()
        try:
            await member.add_roles(*newroles)
        except discord.Forbidden:
            return await interaction.followup.send(
                "I don't have permission to add roles to that member", ephemeral=True
            )
        except discord.HTTPException as e:
            return await interaction.followup.send(str(e), ephemeral=True)
        s = f"Added the following roles to {member.mention}: {' ,'.join([r.mention for r in newroles])}"
        if failed:
            s += f'\nand failed to add: {" ,".join([r.mention for r in failed])}'
        await interaction.followup.send(
            s, allowed_mentions=discord.AllowedMentions(roles=False)
        )

    async def remove_autocomplete(self, interaction: discord.Interaction, current: str):
        if interaction.namespace.member is None:
            return []
        member = interaction.guild.get_member(interaction.namespace.member.id)
        if member is None:
            return []
        roles = member.roles
        toreturn = []
        for role in roles:
            if not role.is_assignable():
                continue
            if role.name.lower().startswith(current.lower()):
                toreturn.append(app_commands.Choice(name=role.name, value=str(role.id)))

        return toreturn[:25]

    @app_commands.command(name="remove", description="Removes a role from a member")
    @app_commands.describe(
        member="The member to remove the role from",
        role="The role to remove, only one at a time",
    )
    @app_commands.autocomplete(role=remove_autocomplete)
    async def _remove(
        self, interaction: discord.Interaction, member: discord.Member, role: str
    ):
        try:
            role = await RoleConverter().convert(
                (await self.bot.get_context(interaction)), role
            )
        except commands.RoleNotFound:
            return await interaction.response.send_message(
                f"I couldn't find this role: {role}", ephemeral=True
            )
        if not interaction.user.guild_permissions.manage_roles:
            return await interaction.response.send_message(
                "You are missing the manage roles permission to do that", ephemeral=True
            )
        try:
            await member.remove_roles(role)
        except Forbidden:
            return await interaction.response.send_message(
                f"I don't have permissions to do that", ephemeral=True
            )
        except HTTPException as e:
            return await interaction.response.send_message(str(e), ephemeral=True)
        await interaction.response.send_message(
            f"Removed {role.mention} from {member.mention}", ephemeral=True
        )


class CustomActivityType(Enum):
    playing = 0
    listening = 2
    watching = 3


class CustomStatus(Enum):
    online = "online"
    offline = "offline"
    idle = "idle"
    dnd = "dnd"


class edit(app_commands.Group):
    """Edits the bot profile"""

    def __init__(self, bot: bot.AndreiBot):
        self.bot = bot
        super().__init__(guild_ids=[testguild_id, mushroom_id])

    @app_commands.command(description="changes the bot's status")
    @app_commands.describe(
        status="the new status",
        description="the new description",
        type="the new activity type",
    )
    async def status(
        self,
        interaction: discord.Interaction,
        status: CustomStatus = None,
        description: app_commands.Range[str, 2, 128] = None,
        type: CustomActivityType = None,
    ):
        if status is not None:
            await self.bot.pool.execute(
                "UPDATE internal_config SET value = $1 WHERE key = 'default_status'",
                str(status.value),
            )

        if description is not None:
            await self.bot.pool.execute(
                "UPDATE internal_config SET value = $1 WHERE key = 'status_description'",
                description,
            )

        if type is not None:
            await self.bot.pool.execute(
                "UPDATE internal_config SET value = $1 WHERE key = 'status_type'",
                str(type.value),
            )

        activity, status = await utils.make_activity(self.bot.pool)
        await self.bot.change_presence(activity=activity, status=status)
        await interaction.response.send_message("changed my status")

    @app_commands.command()
    @app_commands.describe(name="The bot's new username")
    async def username(self, interaction: discord.Interaction, name: str):
        """Changes the bot's username"""
        if interaction.guild.id != 831556458398089217:
            m = self.bot.get_guild(mushroom_id).get_member(interaction.user.id)
            can_run = m.get_role(777982059565154315)
            if not can_run:
                return await interaction.response.send_message(
                    "You're not allowed to use this command", ephemeral=True
                )
        try:
            await self.bot.user.edit(username=name)
        except Exception as e:
            mes = str(e)
        else:
            mes = f"Changed my username to {name}"
        finally:
            await interaction.response.send_message(mes)

    @app_commands.command()
    @app_commands.describe(
        image="Gifs are supported, but will be converted to static pngs"
    )
    async def avatar(
        self, interaction: discord.Interaction, image: discord.Attachment = None
    ):
        """Edits the bot's profile picture, if image is a missing argument the bot's avatar will be removed"""
        if interaction.guild.id != 831556458398089217:
            m = self.bot.get_guild(mushroom_id).get_member(interaction.user.id)
            can_run = m.get_role(777982059565154315)
            if not can_run:
                return await interaction.response.send_message(
                    "You're not allowed to use this command", ephemeral=True
                )
        await interaction.response.defer()
        if image:
            img = await image.read()
        else:
            img = None
        try:
            await self.bot.user.edit(avatar=img)
            mes = "Edited my avatar"
        except Exception as e:
            mes = str(e)
        await interaction.followup.send(mes)


class Slashcommands(commands.Cog):
    def __init__(self, bot: bot.AndreiBot) -> None:
        super().__init__()
        self.bot = bot

    async def cog_load(self) -> None:
        tree = self.bot.tree
        tree.add_command(edit(self.bot))
        tree.add_command(role(self.bot))
        tree.add_command(snipe(self.bot))
        tree.add_command(purge(self.bot))
        tree.on_error = on_error

        @tree.context_menu(name="translate from british")
        async def fix_grammar(
            interaction: discord.Interaction, message: discord.Message
        ):
            if not message.content:
                return await interaction.response.send_message(
                    "This message has no content", ephemeral=True
                )
            await interaction.response.defer()
            async with self.bot.session.get(
                "https://api.yodabot.xyz/api/grammar-correction/correct",
                params={"text": message.clean_content},
            ) as resp:
                res = await resp.json()
            if not res["different"]:
                return await interaction.followup.send("This message is fine")
            embed = discord.Embed(
                color=discord.Color.orange(), title="Original", url=message.jump_url
            )
            embed.set_author(
                name=message.author, icon_url=message.author.display_avatar
            )
            desc = res["corrected"]
            if len(desc.split("\n\n")) > 1:
                desc = "\n\n".join(desc.split("\n\n")[1:])

            embed.description = desc
            await interaction.followup.send(embed=embed)

        @app_commands.allowed_installs(guilds=True, users=True)
        @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
        @tree.context_menu(name="view avatar")
        async def avatar_contextmenu(
            interaction: discord.Interaction, member: discord.Member
        ):
            embed = discord.Embed(color=discord.Color.orange())
            if member.avatar:
                av = member.avatar
                avatar_type = ""
            elif member.guild_avatar:
                av = member.guild_avatar
                avatar_type = " server"
            else:
                av = member.default_avatar
                avatar_type = " default"
            embed.set_image(url=av.with_size(4096))
            embed.set_author(name=f"{member}'s{avatar_type} avatar")
            embed.set_footer(text=f"ID: {member.id}")
            await interaction.response.send_message(
                embed=embed,
            )

        @tree.context_menu(name="steal emojis")
        async def stealemojis(
            interaction: discord.Interaction, message: discord.Message
        ):
            if not interaction.user.guild_permissions.manage_emojis:
                return await interaction.response.send_message(
                    "You are missing the `manage emojis` permissions", ephemeral=True
                )
            if not message.content:
                return await interaction.response.send_message(
                    "This message has no content", ephemeral=True
                )
            emojis = []

            def get_emoji(arg):
                match = re.match(r"<(a?):([a-zA-Z0-9\_]{1,32}):([0-9]{15,20})>$", arg)
                if match:
                    return discord.PartialEmoji.with_state(
                        state=interaction.client._connection,
                        name=match.group(2),
                        animated=bool(match.group(1)),
                        id=int(match.group(3)),
                    )
                return None

            pattern = r"<?a?:[a-zA-Z0-9\_]{1,32}:[0-9]{15,20}>?"
            s = re.findall(pattern, message.content)
            s = list(set(s))
            for match in s:
                emoji = get_emoji(match)
                if emoji:
                    if emoji in emojis:
                        continue
                    emojis.append(emoji)

            if len(emojis) == 0:  # no emojis found
                return await interaction.response.send_message(
                    "I couldn't find any emoji", ephemeral=True
                )

            elif len(emojis) == 1:  # one emoji, no confirmation needed
                emoj: discord.PartialEmoji = emojis[0]
                try:
                    new_emoji = await interaction.guild.create_custom_emoji(
                        name=emoj.name, image=(await emoj.read())
                    )
                    em = discord.Embed(
                        color=discord.Color.green(),
                        description=f"done {new_emoji}\nname: {new_emoji.name}\nID: {new_emoji.id}\nanimated: {new_emoji.animated}\n`{new_emoji}`",
                    )
                    em.set_thumbnail(url=new_emoji.url)
                    await interaction.response.send_message(embed=em)
                except (Forbidden, HTTPException) as e:
                    await interaction.response.send_message(str(e))
                return

            else:  # ask for confirmation
                if len(emojis) > 30:
                    emojis = emojis[:30]
                    s = "(limited to 30 to avoid rate limits)"
                else:
                    s = ""
                mock = await interaction.client.get_context(interaction)
                view = utils.ConfirmationView(ctx=mock)
                await interaction.response.send_message(
                    f"This will add {len(emojis)} emojis to this server, are you sure? {s}",
                    view=view,
                )
                await view.wait()
                if not view.value:  # doesn't want to add them
                    return await interaction.edit_original_response(
                        content="\U0001f44d"
                    )
                done = 0
                for emoji in emojis:
                    try:
                        await interaction.guild.create_custom_emoji(
                            name=emoji.name, image=(await emoji.read())
                        )
                        done += 1
                    except (Forbidden, HTTPException) as e:
                        pass
                await interaction.followup.send(f"Added {done} emojis")


        @app_commands.allowed_installs(guilds=True, users=True)
        @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
        @tree.context_menu(name="view banner")
        async def viewbanner(interaction: discord.Interaction, member: discord.Member):
            user = await self.bot.fetch_user(member.id)
            if not user.banner:
                return await interaction.response.send_message(
                    "This user has no banner, bots don't have access to server specific banners btw",
                    ephemeral=True,
                )
            em = discord.Embed(color=discord.Color.orange())
            em.set_author(name=f"{user}'s banner", icon_url=user.display_avatar)
            em.set_image(url=user.banner)
            await interaction.response.send_message(
                embed=em,
                ephemeral=True,
                view=discord.ui.View().add_item(utils.url_button(user)),
            )

        return await super().cog_load()

    async def cog_unload(self) -> None:
        tree = self.bot.tree
        tree.remove_command("edit")
        tree.remove_command("role")
        tree.remove_command("steal emojis")
        tree.remove_command("view banner")
        tree.remove_command("view avatar")
        tree.remove_command("fix grammar")
        tree.remove_command("snipe")
        tree.remove_command("purge")
        return await super().cog_unload()

    async def channel_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        current = current.lower()
        toreturn = []
        complete = []
        channels = [
            channel for guild in self.bot.guilds for channel in guild.text_channels
        ]

        try:
            channelid = str(int(current))
        except ValueError:
            channelid = None

        for channel in interaction.guild.text_channels:
            s = [c.id for c in toreturn]
            if channel.id in s:
                continue
            if current in channel.name.lower():
                toreturn.append(channel)
                complete.append(
                    app_commands.Choice(value=str(channel.id), name=channel.name)
                )

        for channel in channels:
            s = [u.id for u in toreturn]
            if channel.id in s:
                continue
            if current in channel.name.lower():
                complete.append(
                    app_commands.Choice(
                        value=str(channel.id),
                        name=f"{channel.name} (SERVER: {channel.guild.name})",
                    )
                )
                toreturn.append(channel)

        if channelid:
            for channel_id in [str(channel.id) for channel in channels]:
                if channelid in channel_id:
                    chan = self.bot.get_channel(int(channel_id))
                    if channel in interaction.guild.text_channels:
                        complete.append(
                            app_commands.Choice(value=str(chan.id), name=chan.name)
                        )
                    else:
                        complete.append(
                            app_commands.Choice(
                                value=str(chan.id),
                                name=f"{chan.name} (SERVER: {chan.guild.name})",
                            )
                        )
                    toreturn.append(chan)

        return complete[:25]

    @app_commands.command(description="Sends a message through the bot")
    @app_commands.describe(
        channel="The target channel (use the autocomplete or it breaks (i'm lazy))",
        content="The message's content",
        file="An optional attachment",
        reference="The message ID the bot is replying to, MUST be in the chosen channel",
    )
    @app_commands.autocomplete(channel=channel_autocomplete)
    @app_commands.guilds(testguild, mushroom)
    async def message(
        self,
        interaction: discord.Interaction,
        channel: str,
        content: str = None,
        file: discord.Attachment = None,
        reference: str = None,
    ):
        if (content is None) and (file is None):
            return await interaction.response.send_message(
                "I can't send an empty message", ephemeral=True
            )

        destination = self.bot.get_channel(int(channel))

        if destination is None:
            return await interaction.response.send_message(
                f"I couldn't find channel with ID: {channel}", ephemeral=True
            )

        if reference:
            try:
                refid = int(reference)
            except ValueError:
                return await interaction.response.send_message(
                    f"{refid} is an invalid number", ephemeral=True
                )
            try:
                ref = await destination.fetch_message(refid)
            except NotFound:
                return await interaction.response.send_message(
                    f"{refid} is not a message in this channel or an invalid ID",
                    ephemeral=True,
                )
        else:
            ref = None

        if file:
            await interaction.response.defer(thinking=True, ephemeral=True)
            file = await file.to_file()

        try:
            m = await destination.send(content=content, file=file, reference=ref)
        except (TypeError, ValueError, Forbidden, HTTPException) as e:
            if interaction.response.is_done():
                return await interaction.followup.send(str(e))
            return await interaction.response.send_message(str(e), ephemeral=True)
        resp = f"I sent a message in {destination.mention} - {m.jump_url}"
        if interaction.response.is_done():
            await interaction.followup.send(resp)
        else:
            await interaction.response.send_message(resp, ephemeral=True)

    @app_commands.command(description="Sends a DM through the bot")
    @app_commands.describe(content="The message content", file="An optional attachment")
    @app_commands.guilds(testguild, mushroom)
    async def dm(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        content: str = None,
        file: discord.Attachment = None,
    ):
        if (content is None) and (file is None):
            can_dm = await check_dms(user)
            if can_dm:
                res = "I can DM"
            else:
                res = "I can't DM"
            return await interaction.response.send_message(
                f"{res} {user} (ID: {user.id})", ephemeral=True
            )
        await interaction.response.defer()
        if file:
            file = await file.to_file()
        try:
            await user.send(content, file=file)
        except discord.HTTPException as e:
            if e.code == 50006:
                return await interaction.followup.send(
                    "Cannot send an empty message", ephemeral=True
                )
            elif e.code == 50007:
                return await interaction.followup.send(
                    "Cannot DM this user", ephemeral=True
                )
            else:
                return await interaction.followup.send(e)
        except (TypeError, ValueError, Forbidden) as e:
            return await interaction.followup.send(e, ephemeral=True)
        await interaction.followup.send(f"Sent a DM to {user} (ID: {user.id})")

    @app_commands.command(
        description="Converts the date to a discord timestamp, UTC timezone",
        name="timestamp",
    )
    @app_commands.describe(
        date="format 'DD/MM/YEAR hh:mm:ss', \
        hh:mm:ss",
        style="The format style",
    )
    @app_commands.choices(style=DatesStyles)
    async def _timestamp(
        self,
        interaction: discord.Interaction,
        date: str,
        style: app_commands.Choice[str] = None,
    ):
        if not ":" in date:
            date += " 00:00:00"
        try:
            dtime = datetime.datetime.strptime(date, "%d/%m/%Y %H:%M:%S")
        except ValueError:
            return await interaction.response.send_message(
                f"'{date}' does not match format DD/MM/YEAR hh:mm:ss (example: 21/03/2005 15:31:50)",
                ephemeral=True,
            )
        if style is None:
            style = app_commands.Choice(name="Timestamp", value="None")
        if style.value == "None":
            return await interaction.response.send_message(int(dtime.timestamp()))

        s = f"{discord.utils.format_dt(dtime, style.value)}"
        await interaction.response.send_message(s)


    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(description="View member banners")
    @app_commands.describe(target="Your target, fill with ID if outside the server")
    async def banner(
        self,
        interaction: discord.Interaction,
        target: typing.Optional[discord.User] = None,
    ):
        if target is None:
            target = interaction.user
        user = await self.bot.fetch_user(target.id)  # should never error?
        if user.banner is None:
            return await interaction.response.send_message(
                f"{target} has no banner", ephemeral=True
            )
        banner = user.banner
        embed = discord.Embed(color=discord.Color.orange())
        embed.set_author(name=target, icon_url=target.display_avatar)
        embed.set_image(url=banner.with_size(4096))
        await interaction.response.send_message(embed=embed)



    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(
        description="View any discord user's avatar"
    )
    @app_commands.describe(
        user="The target user, fill with ID if outside the server",
        type="The avatar type",
    )
    async def avatar(
        self,
        interaction: discord.Interaction,
        user: discord.User = None,
        type: typing.Literal["server", "profile", "default"] = "profile",
    ):
        if user is None:
            user = interaction.user
        em = discord.Embed(color=discord.Color.orange())
        if type == "server":
            member = interaction.guild.get_member(user.id)
            if member is None:
                return await interaction.response.send_message(
                    f"{user} isn't in this server", ephemeral=True
                )
            if member.guild_avatar is None:
                return await interaction.response.send_message(
                    "This member has no server avatar", ephemeral=True
                )
            em.title = f"{user}'s server avatar"
            em.set_author(name=member, icon_url=member.guild_avatar)
            em.set_image(url=member.guild_avatar)
        elif type == "profile":
            em.title = f"{user}'s avatar"
            av = user.avatar or user.default_avatar
            em.set_author(name=user, icon_url=av)
            em.set_image(url=user.display_avatar)
        else:
            em.title = f"{user}'s default avatar"
            em.set_author(name=user, icon_url=user.default_avatar)
            em.set_image(url=user.default_avatar)
        await interaction.response.send_message(embed=em)



    @app_commands.command(
        name="setlogchannel",
        description="Sets the channel for server logs, no more configuration required",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        channel="The channel to log to, if not given then the bot stops logging for this srever"
    )
    async def set_log_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel = None
    ):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message(
                "You're missing permissions", ephemeral=True
            )
        await self.bot.pool.execute(
            f"DELETE FROM log_channels WHERE server_id = {interaction.guild.id}"
        )
        if channel is not None:
            await self.bot.pool.execute(
                "INSERT INTO log_channels (server_id, channel_id) VALUES ($1, $2) ON CONFLICT (server_id) DO UPDATE SET channel_id=excluded.channel_id",
                interaction.guild.id,
                channel.id,
            )
        await interaction.response.send_message("done \U0001f44d")
        await self.bot.cogs["Logs"].load_channels()


    @app_commands.command(
        name="setinvitelog",
        description="Sets the channel for the invite logger, no more configuration required",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        channel="The channel to log invites to, if not given then the bot stops logging invites for this srever"
    )
    async def invite_log(
        self, interaction: discord.Interaction, channel: discord.TextChannel = None
    ):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message(
                "You're missing permissions", ephemeral=True
            )
        await self.bot.pool.execute(
            f"DELETE FROM invite_logchannel WHERE server_id = {interaction.guild.id}"
        )
        if channel is not None:
            await self.bot.pool.execute(
                "INSERT INTO invite_logchannel (server_id, channel_id) VALUES ($1, $2) ON CONFLICT (server_id) DO UPDATE SET channel_id=excluded.channel_id",
                interaction.guild.id,
                channel.id,
            )
        await interaction.response.send_message("done \U0001f44d")
        await self.bot.cogs["events"].update_invites.__call__()

    async def guild_autocomplete(self, interaction: discord.Interaction, current: str):
        toreturn = []
        if "local" in current.lower():
            toreturn.append(
                app_commands.Choice(
                    name=interaction.guild.name, value=str(interaction.guild.id)
                )
            )
        for guild in interaction.client.guilds:
            if current.lower() in guild.name.lower():
                toreturn.append(
                    app_commands.Choice(name=guild.name, value=str(guild.id))
                )

        return toreturn[:25]

    @app_commands.command(name="sync", description="Syncs the slash commands")
    @app_commands.autocomplete(guild=guild_autocomplete)
    @app_commands.guilds(testguild, mushroom)
    @app_commands.describe(guild="Target server, syncs globally if not given")
    async def _sync(
        self, interaction: discord.Interaction, guild: typing.Optional[str]
    ):
        if guild:
            try:
                guild = await GuildConverter().convert(
                    (await self.bot.get_context(interaction)), guild
                )
            except (commands.BadArgument, HTTPException) as e:
                return await interaction.response.send_message(e, ephemeral=True)
            newcommands = await self.bot.tree.sync(guild=guild)
            tp = f"in {guild.name}"
        else:
            newcommands = await self.bot.tree.sync()
            tp = "globally"
        await interaction.response.send_message(
            f"Synced {len(newcommands)} commands {tp}"
        )

    @app_commands.command(name="meme", description="Generates a meme given the image")
    @app_commands.describe(
        image="The image to work on",
        toptext="Text to show at the top",
        bottomtext="Text to show at the bottom",
    )
    async def _meme(
        self,
        interaction: discord.Interaction,
        image: discord.Attachment,
        toptext: str = None,
        bottomtext: str = None,
    ):
        if not image.filename.endswith(("png", "jpg", "jpeg", "gif")):
            return await interaction.response.send_message(
                "Unsupported file type", ephemeral=True
            )
        await interaction.response.defer()
        headers = {"API-KEY": "ea103fd19b9e7b5f75c09727d8c707"}
        url = "https://memebuild.com/api/1.0/generateMeme"
        data = {
            "topText": toptext if toptext else "",
            "bottomText": bottomtext if bottomtext else "",
            "imgUrl": image.url,
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(url, data=data) as response:
                if response.status != 200:
                    return await interaction.followup.send(await response.text())
                dt = await response.json()

        await interaction.followup.send(dt["url"])

    @app_commands.command(description="Unbans a user from this server")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.describe(
        user="The user to unban, this autocompletes with banned users",
        reason="The optional reason",
    )
    async def unban(
        self, interaction: discord.Interaction, user: str, reason: str = None
    ):
        if not interaction.user.guild_permissions.ban_members:
            return await interaction.response.send_message(
                f"You are missing the `ban members` permissions", ephemeral=True
            )
        if reason is None:
            reason = f"Done by {interaction.user} (ID: {interaction.user.id})"
        else:
            reason += f"Done by {interaction.user} (ID: {interaction.user.id})"
        try:
            banentry = await interaction.guild.fetch_ban(discord.Object(id=int(user)))
        except NotFound:
            return await interaction.response.send_message(f"{user} is not banned")
        try:
            await interaction.guild.unban(banentry.user, reason=reason)
        except NotFound:
            return await interaction.response.send_message(f"{user} is not banned")
        await interaction.response.send_message(
            f"unbanned {banentry.user} (ID: {banentry.user.id})"
        )

    @unban.autocomplete("user")
    async def unban_user_entry(self, interaction: discord.Interaction, current: str):
        if not interaction.guild.me.guild_permissions.ban_members:
            return []
        bans = [ban async for ban in interaction.guild.bans()]

        current = current.lower()
        toreturn = []
        complete = []

        try:
            userid = str(int(current))
        except ValueError:
            userid = None

        for entry in bans:
            s = [u.id for u in toreturn]
            if entry.user.id in s:
                continue
            if current in str(entry.user).lower():
                complete.append(
                    app_commands.Choice(value=str(entry.user.id), name=str(entry.user))
                )
                toreturn.append(entry.user)

        if userid:
            for user_id in [str(user.id) for user in [entry.user for entry in bans]]:
                if userid in user_id:
                    us = discord.utils.find(
                        lambda entry: entry.user.id == int(user_id), bans
                    )
                    if us:
                        complete.append(
                            app_commands.Choice(
                                value=str(us.user.id), name=str(us.user)
                            )
                        )
                        toreturn.append(us.user)

        return complete[:25]

    async def member_autocomplete(self, interaction: discord.Interaction, current: str):
        current = current.lower()
        toreturn = []
        complete = []

        try:
            userid = str(int(current))
        except ValueError:
            userid = None

        for member in interaction.guild.members:
            if not member.is_timed_out():
                continue
            s = [u.id for u in toreturn]
            if member.id in s:
                continue
            if current.lower() in str(member).lower():
                toreturn.append(member)
                complete.append(
                    app_commands.Choice(value=str(member.id), name=str(member))
                )

        if userid:
            for user_id in [
                str(user.id)
                for user in interaction.guild.members
                if user.is_timed_out()
            ]:
                if userid in user_id:
                    us = interaction.guild.get_member(int(user_id))
                    complete.append(app_commands.Choice(value=str(us.id), name=str(us)))
                    toreturn.append(us)

        return complete[:25]

    @app_commands.command(
        description="Unmutes a timed out user",
    )
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(
        member="The member to unmute, this autocompletes with muted users"
    )
    @app_commands.autocomplete(member=member_autocomplete)
    async def unmute(self, interaction: discord.Interaction, member: str):

        if not interaction.user.guild_permissions.moderate_members:
            return await interaction.response.send_message(
                "You are missing the `moderate members` perms", ephemeral=True
            )

        mock_ctx = await self.bot.get_context(interaction)
        try:
            member: discord.Member = await utils.MemberConverter().convert(
                mock_ctx, member
            )
        except commands.MemberNotFound:
            return await interaction.response.send_message(
                f"I couldn't find member {member} in this server", ephemeral=True
            )

        if (member.top_role > interaction.user.top_role) and (
            interaction.user != interaction.guild.owner
        ):
            return await interaction.response.send_message(
                f"{member}'s top role is higher than yours", ephemeral=True
            )

        try:
            await member.timeout(
                None,
                reason=f"unmuted by {interaction.user} (ID: {interaction.user.id})",
            )
        except discord.Forbidden:
            return await interaction.response.send_message(
                f"I don't have perms to unmute {member.mention}", ephemeral=True
            )
        await interaction.response.send_message(f"unmuted {member.mention}")


async def setup(bot: bot.AndreiBot):
    await bot.add_cog(Slashcommands(bot))
