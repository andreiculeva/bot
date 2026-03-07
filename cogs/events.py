import re
import discord
from discord.ext import commands, tasks
import asyncio
import typing
import bot
import utils
import traceback
from discord.ext.commands.errors import (
    CommandNotFound,
    MemberNotFound,
    MissingPermissions,
    MissingRequiredArgument,
    RoleNotFound,
    UserNotFound,
)
import datetime
import random

never_text = """[2-0 1v1](https://cdn.discordapp.com/attachments/1259352820998606879/1286049799430475897/Desktop_2024.09.18_-_20.29.44.09_-_Trim.mp4?ex=675353b5&is=67520235&hm=fa4aa74778e723d1990e894528a74a4a683f741aed65d79642a5c7aa6f5ebf58&)
[3-0 3v3](https://media.discordapp.net/attachments/644571546769424384/1285717657680740450/2024-09-17_22-33-49_-_Trim.mp4?ex=67536fe1&is=67521e61&hm=ac73121503ae60d1ae23082f66e46d46f5498d80e2ecee81fa7c00234699a503&)
[ugly poor](https://media.discordapp.net/attachments/846138076836397058/1312238164341035018/image.png?ex=6753ad86&is=67525c06&hm=9860557ea8c942c3cfa7d16ad09e5bba9ec14186c172ff9c2d2c24fe11d89fff&=&format=webp&quality=lossless)
[ugly poor](https://media.discordapp.net/attachments/846143258195001364/1314444498801004564/image.png?ex=6753cb55&is=675279d5&hm=09710ef7a20058f726f19772ff8cc434dcc5da1590239aed7391a9a73676b85a&=&format=webp&quality=lossless)"""


insults_list = """
{user} is the human equivalent of a participation trophy.
{user} is the reason the gene pool needs a lifeguard.
{user} is an absolute fucking donut.
{user} is about as useful as a screen door on a submarine.
I've had smarter conversations with a goddamn brick wall than I have with {user}.
{user} is a monumental waste of skin.
If ignorance is bliss, {user} must be the happiest motherfucker on Earth.
{user} has the personality of a damp cloth.
I would call {user} a cunt, but they lack both the warmth and the depth.
{user} is the type of asshole to leave 1 second on the microwave.
{user} isn't the sharpest tool in the shed; they're not even in the goddamn shed.
{user}'s family tree must be a cactus because everyone on it is a prick.
{user} is an insufferable twat.
I envy everyone {user} has never met.
If {user}'s brain was dynamite, there wouldn't be enough to blow their fucking hat off.
{user} is the human equivalent of a dial-up modem sound.
{user} is a gaping abscess who needs to learn when to shut their mouth.
{user} is as bright as a black hole, and twice as dense.
I've forgotten more than {user} will ever know, the simple bastard.
{user} couldn't pour water out of a boot with instructions on the heel.
{user} is a fucking oxygen thief.
{user} looks like their face was set on fire and someone tried to put it out with a fork.
{user} is an absolute muppet.
{user} has a room-temperature IQ... in Celsius.
{user} is the after-photo in a "don't do drugs" campaign.
{user} is less of a person and more of a fucking problem.
Someone needs to pop {user} with a fucking pin, the massive balloon of ego.
{user} is a goddamn troglodyte.
{user} is the kind of person who claps when the plane lands.
{user}'s thought process is a tangled fucking mess of Christmas lights.
{user} is the human version of a Monday morning.
I'd agree with {user}, but then we'd both be wrong, the dumb shit.
{user} is a f—king waste of a perfectly good asshole.
Every time {user} talks, they lower the IQ of the entire room.
{user} is the human equivalent of getting your sock wet.
{user} is an absolute cockwomble.
If I wanted to kill myself, I'd climb {user}'s ego and jump to their IQ.
{user} is as useful as a poopy-flavored lollipop.
{user} is a B-list celebrity in their own fucking life story.
{user} is an utter shit-gibbon.
{user} couldn't organize a piss-up in a brewery.
{user} is proof that God has a sense of humor, and it's fucking twisted.
{user} isn't a clown, they're the entire goddamn circus.
Somewhere out there, a tree is tirelessly producing oxygen for {user}. They owe it an apology.
{user} is a vacuous, mouth-breathing cretin.
{user}'s own reflection called the cops on them.
I bet {user} thinks "cumbersome" is a variety of fucking vegetable.
{user} is a bigger disappointment than the last season of Game of Thrones.
{user} is an absolute douche-canoe.
{user}'s face looks like it was used to extinguish a campfire.
I'm not saying I hate {user}, but I would unplug their life support to charge my phone.
{user} is a fucking nincompoop.
{user} is the reason we have warning labels on everything.
{user} has the charisma of a damp rag.
{user} is a stale breadstick of a person.
{user} is a grey-scale painting in a world of fucking color.
{user} is an utter, utter bastard.
{user} is the personification of a 404 error: personality not found.
{user} is so dense, light bends around them.
{user} looks like they were beaten with an ugly stick.
If {user} were a spice, they'd be fucking flour.
{user} is about as interesting as a blank sheet of paper.
{user} has all the charm of a dead fish.
Calling {user} a tool is a fucking insult to hammers everywhere.
{user} is a fart in a jar.
I've seen more intelligent life on a slice of moldy bread than in {user}.
{user} is a worthless sack of shit.
{user} is ten pounds of crap in a five-pound bag.
{user} is the result of a participation award being given at an orgy.
I would roast {user}, but my mom told me not to burn trash.
{user} brings everyone a lot of joy… when they leave the fucking room.
{user} is the answer to a question no one fucking asked.
{user} could be replaced by a houseplant and no one would notice the difference for a week.
{user} is a fucking bellend.
If I had a face like {user}'s, I'd sue my parents.
{user} is a walking, talking argument for abortion.
{user} is the human equivalent of a traffic jam.
{user} is the reason they invented the middle finger.
{user} is a fucking chode.
{user} is a half-eaten bag of soggy dicks.
I've met doorstops with more personality than {user}.
{user} is a fucking liability to the human race.
{user} is a pathetic excuse for a mammal.
{user} is a two-bit, no-account, bottom-feeding shit-heel.
{user} is a few fries short of a Happy Meal.
{user} is the human equivalent of a glitter bomb—messy and impossible to get rid of.
{user} is an absolute tosser.
{user} is so fucking boring, my paint is watching them dry.
{user} is a sad, strange little person, and they have my pity.
{user} couldn't hit water if they fell out of a fucking boat.
{user} is a stain on the underwear of society.
I hope {user}'s day is as pleasant as they are.
{user} is the poster child for why some animals eat their young.
{user} is a festering pustule on the ass of humanity.
{user} isn't just a dipshit; they're the whole fucking dip.
{user} is an inspiration for birth control.
{user} is a blithering idiot.
{user} is a fucking wanker.
{user} is the weakest link. Goodbye.
Honestly, {user} should just fuck off.
""".splitlines()


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
        self.invite_channels = {}  # server_id : channel_id
        self.update_invites.start()
        self.gm_msg.start()
        self.gn_msg.start()
        self.birthday_announcer.start()

    def cog_unload(self):
        self.update_invites.cancel()
        self.gm_msg.cancel()
        self.gn_msg.cancel()
        self.birthday_announcer.cancel()

    @tasks.loop(time=datetime.time(hour=6))
    async def birthday_announcer(self):
        """Task that announces birthdays every day at 9:00 AM (Italian time)"""
        today = datetime.date.today()
        entries = await self.bot.pool.fetch(
            "SELECT channel_id FROM birthday_channels"
        )
        for entry in entries:
            channel = self.bot.get_channel(entry["channel_id"])
            if channel is None:
                continue

            birthdays = await self.bot.pool.fetch(
                """
                SELECT user_id FROM birthdays
                WHERE EXTRACT(MONTH FROM date) = $1 AND EXTRACT(DAY FROM date) = $2
                """,
                today.month,
                today.day,
            )

            if not birthdays:
                continue

            mentions = []
            for record in birthdays:
                member = channel.guild.get_member(record["user_id"])
                if member:  # Controlla se l'utente è nel server
                    mentions.append(member.mention)

            if not mentions:
                continue
            message = f"🎉 Happy Birthday {', '.join(mentions)}! 🎂"

            # Invia il messaggio nel canale
            await channel.send(message)

    def get_random_user(self, guild:discord.Guild):
        return random.choice([x for x in guild.members if not x.bot])

    def get_insult(self, user:discord.User) -> str:
        return random.choice(insults_list).replace("{user}", user.mention)

    @birthday_announcer.before_loop
    async def before_birthday_announcer(self):
        await self.bot.wait_until_ready()

    @tasks.loop(time=datetime.time(hour=10))
    async def gm_msg(self):
        """Task that runs every day at 8:00 AM (Italian time)"""
        channel_id = 785651298090614784
        channel = self.bot.get_channel(channel_id)

        if channel is None:
            return

        now = datetime.datetime.now()
        eight_hours_ago = now - datetime.timedelta(hours=10)

        unique_authors: list[discord.User] = []
        async for message in channel.history(after=eight_hours_ago, oldest_first=True):
            if message.author.bot:
                continue
            if any(
                word in message.content.lower()
                for word in ["gm", "morning", "good morning"]
            ):
                if message.author not in unique_authors:
                    unique_authors.append(message.author)

        if unique_authors:
            author_names = ", ".join(
                (author.global_name or author.name) for author in unique_authors
            )
            await channel.send(f"Good morning {author_names}!")
        else:
            text = self.get_insult(self.get_random_user(channel.guild))
            await channel.send(text)

    @gm_msg.before_loop
    async def before_gm_msg(self):
        await self.bot.wait_until_ready()

    @tasks.loop(time=datetime.time(hour=22))
    async def gn_msg(self):
        """Task that runs every day at 23:00  (Italian time)"""
        print("running task")
        channel_id = 785651298090614784
        channel = self.bot.get_channel(channel_id)

        if channel is None:
            return

        now = datetime.datetime.now()
        eight_hours_ago = now - datetime.timedelta(hours=10)

        unique_authors: list[discord.User] = []
        async for message in channel.history(after=eight_hours_ago, oldest_first=True):
            if message.author.bot:
                continue
            if any(
                word in message.content.lower()
                for word in ["gn", "night", "good night"]
            ):
                if message.author not in unique_authors:
                    unique_authors.append(message.author)
        print("made it this far")
        if unique_authors:
            author_names = ", ".join(
                (author.global_name or author.name) for author in unique_authors
            )
            await channel.send(f"Good night {author_names}!")
        else:
            text = self.get_insult(self.get_random_user(channel.guild))
            await channel.send(text)

    @gn_msg.before_loop
    async def before_gn_msg(self):
        await self.bot.wait_until_ready()

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
        elif isinstance(error, commands.errors.CommandInvokeError):
            em.description = str(error)
        elif isinstance(error, commands.CommandInvokeError):
            em.description = str(error)
        elif isinstance(error, MissingPermissions):
            if ctx.author.id in ctx.bot.owner_ids:
                await ctx.reinvoke(restart=True)  # bypass owners
                return
            x = ", ".join(
                [f"`{p.replace('_', ' ')}`" for p in error.missing_permissions]
            )
            em.description = f"You are missing the {x} perms"
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
    
    def get_gif_url_from_message(self, msg: discord.Message):
        # 1) direct uploaded GIF
        return msg.content + ".gif"


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
            lambda t: ("starboard" in t.name.lower()), channel.guild.text_channels
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
                .filename
                .lower()
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
                if attachment.filename.lower().endswith(
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
        if not image_set:
            gif_url = self.get_gif_url_from_message(message)
            if gif_url:
                em.set_image(url=gif_url)
                image_set = True
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

    @commands.Cog.listener(name="on_message")
    async def counter(self, message: discord.Message):
        if message.channel.id not in (
            928597369111576597,
            715986355485933619,
            846257527678697502,
        ):
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
        self.invite_channels = {}
        for server_id, channel_id in data:
            self.invite_channels[server_id] = channel_id

        # list of the old server invites
        invite_servers = list(self.invites.keys())
        for server_id in invite_servers:
            if server_id not in self.invite_channels.keys():
                del self.invites[server_id]
                del self.vanities[server_id]

        for server_id, channel_id in self.invite_channels.items():
            log_channel = self.bot.get_channel(channel_id)
            if log_channel is None:
                await self.bot.pool.execute(
                    "DELETE FROM invite_logchannel WHERE channel_id = $1", channel_id
                )  # cleanup line very important
                continue
            try:
                self.invites[server_id] = await log_channel.guild.invites()
            except (discord.Forbidden, discord.HTTPException):
                self.invites[server_id] = []

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
            self.invite_channels[server_id] = channel_id
            log_channel = self.bot.get_channel(channel_id)
            if log_channel is None:
                await self.bot.pool.execute(
                    "DELETE FROM invite_logchannel WHERE channel_id = $1", channel_id
                )  # cleanup line very important
                continue
            try:
                self.invites[server_id] = await log_channel.guild.invites()
            except (discord.Forbidden, discord.HTTPException):
                self.invites[server_id] = []

            try:
                self.vanities[server_id] = await log_channel.guild.vanity_invite()
            except (discord.Forbidden, discord.HTTPException):
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
        if not member.guild.id in self.invite_channels.keys():
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
                em.description = f"I couldn't figure out how they joined"
            else:
                if vanity.uses < new_vanity.uses:
                    em.description = f"ID: {member.id}\nJoined with the vanity URL (.gg/{new_vanity.code})"
                    self.vanities[member.guild.id] = new_vanity
                else:
                    em.description = f"I couldn't figure out how they joined"
        else:
            em.description = f"I couldn't figure out how they joined"
        em.description += (
            f"\nAccount created: {discord.utils.format_dt(member.created_at, 'R')}"
        )
        await self.bot.get_channel(self.invite_channels[member.guild.id]).send(embed=em)
        self.invites[member.guild.id] = await member.guild.invites()

    @commands.Cog.listener(name="on_member_remove")
    async def memberremovercheckidk(self, member: discord.Member):
        if not member.guild.id in self.invite_channels.keys():
            return
        em = discord.Embed(color=discord.Color.red())
        em.set_author(name=member, icon_url=member.display_avatar)
        em.description = f"`{member.id}` left the server"
        em.description += (
            f"\nAccount created: {discord.utils.format_dt(member.created_at, 'R')}"
        )
        await self.bot.get_channel(self.invite_channels[member.guild.id]).send(embed=em)
        self.invites[member.guild.id] = await member.guild.invites()

    @commands.Cog.listener(name="on_invite_create")
    async def inviteupdatecreate(self, invite: discord.Invite):
        if not invite.guild.id in self.invite_channels.keys():
            return
        self.invites[invite.guild.id] = await invite.guild.invites()

    @commands.Cog.listener(name="on_invite_delete")
    async def inviteupdatedelete(self, invite: discord.Invite):
        if not invite.guild.id in self.invite_channels.keys():
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

    @commands.Cog.listener(name="on_member_join")
    async def never_bully(self, member: discord.Member):
        if member.guild.id != 786620405767077919:  # wrs server
            return
        never_id = 923723422574465085
        another_victim = 605398335691554827
        targets = [
            never_id,
        ]
        try:
            targets.index(member.id)
        except ValueError:
            return
        try:
            await member.send(never_text)
        except (discord.Forbidden, discord.HTTPException):
            pass
        await member.kick(reason="2-0 1v1 + 3-0 3v3 + ugly poor")

    @commands.Cog.listener(name="on_message")
    async def add_reactions(self, message: discord.Message):
        """This only adds the reactions"""
        if message.author.bot:
            return
        channel_whitelist = (
            846140294688538634,  # member clips
            1278716164754903151,  # comeback
            846138253157335051,  # clips
            832882989972979723,  # test
        )
        if message.channel.id not in channel_whitelist:
            return
        await asyncio.sleep(3)
        if not (
            message.attachments
            or message.embeds
            or (
                message.message_snapshots
                and message.message_snapshots[0].cached_message
                and (
                    message.message_snapshots[0].cached_message.attachments
                    or message.message_snapshots[0].cached_message.embeds
                )
            )
        ):
            return

        await message.add_reaction("\U0001f525")  # fire emoji
        await message.add_reaction("\U0001f602")  # laugh emoji
        emoji_ids = (
            1283898433345818645,  # bigbrain
            854231053124370482,  # meh
        )
        for emoji_id in emoji_ids:
            em = self.bot.get_emoji(emoji_id)
            if em is not None:
                await message.add_reaction(em)

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
