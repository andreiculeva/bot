"""
docs
https://lavalink.readthedocs.io/en/latest/index.html
"""
import random
import typing
import discord
import lavalink
from discord.ext import commands
import bot
import datetime
from discord import app_commands
import utils
from pytimeparse.timeparse import timeparse


class Music(commands.Cog):
    def __init__(self, bot: bot.AndreiBot):
        self.bot = bot

    def get_player(self, guild: discord.Guild) -> lavalink.DefaultPlayer:
        return self.bot.lavalink.player_manager.create(guild.id)

    async def cog_load(self):
        lavalink.add_event_hook(self.track_hook)

    async def cog_unload(self):
        """Cog unload handler. This removes any event hooks that were registered."""
        self.bot.lavalink._event_hooks.clear()

    async def track_hook(self, event):
        if isinstance(event, lavalink.events.QueueEndEvent):
            # When this track_hook receives a "QueueEndEvent" from lavalink.py
            # it indicates that there are no tracks left in the player's queue.
            # To save on resources, we can tell the bot to disconnect from the voicechannel.
            player: lavalink.DefaultPlayer = event.player
            await player.stop()
            guild = self.bot.get_guild(player.guild_id)
            if guild:
                await guild.voice_client.disconnect(force=True)

    async def cog_before_invoke(self, ctx: commands.Context):
        if ctx.guild is None:
            raise commands.CommandInvokeError("You can't use voice commands in DMs")

        if ctx.author.voice is None:
            raise commands.CommandInvokeError(
                "You must be connected to a voice channel"
            )

        if not ctx.voice_client:
            perms = ctx.author.voice.channel.permissions_for(ctx.me)
            if not perms.connect or not perms.speak:
                raise commands.CommandInvokeError(
                    "I'm missing the `connect` and `speak` permissions"
                )
            await ctx.author.voice.channel.connect(cls=utils.LavalinkVoiceClient)
        elif ctx.voice_client and len(ctx.voice_client.channel.members) == 1:
            await ctx.voice_client.move_to(ctx.author.voice.channel)
        elif ctx.author.voice is not None and ctx.command.name not in ("play", "join"):
            if (
                ctx.voice_client.channel.id != ctx.author.voice.channel.id
                and not ctx.author.guild_permissions.administrator
            ):
                raise commands.CommandInvokeError("You must be in my voice channel")

    @commands.hybrid_command(aliases=["p"])
    @app_commands.describe(query="Can be a Spotify or YouTube song/playlist")
    async def play(
        self,
        ctx: commands.Context,
        *,
        query: typing.Annotated[int, utils.TrackConverter] = None,
    ):
        """Searches and plays a song from a given query."""
        player = self.get_player(ctx.guild)
        if query is None:
            if player.paused:
                await player.set_pause(False)
                return await ctx.send("Resumed")
            else:
                raise commands.CommandInvokeError("I'm not paused")

        embed = discord.Embed(color=discord.Color.orange())
        embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar)
        if query == 1:
            embed.description = (
                f"added [{player.queue[-1].title}]({player.queue[-1].uri}) to the queue"
            )
        else:
            embed.description = f"added {query} tracks to the queue"

        if not player.is_playing:
            await player.play()
        await ctx.send(embed=embed, view=utils.MusicView(self.bot))

    @commands.hybrid_command(aliases=["dc", "leave", "stop"])
    async def disconnect(self, ctx: commands.Context):
        """Disconnects the player from the voice channel and clears its queue."""
        player = self.get_player(ctx.guild)
        player.queue.clear()
        await player.stop()
        await ctx.voice_client.disconnect(force=True)
        await ctx.send("leaving")

    @commands.hybrid_command()
    async def pause(self, ctx: commands.Context):
        """Pauses the player"""
        player = self.get_player(ctx.guild)
        if player.paused:
            raise commands.CommandInvokeError("I'm already paused")
        await player.set_pause(True)
        song = player.current
        if song is None:
            raise commands.CommandInvokeError("I'm not playing anything")
        try:
            if song is not None:
                current_str = datetime.timedelta(seconds=int((player.position) / 1000))
                full_str = datetime.timedelta(seconds=int(song.duration / 1000))
                res = f"{current_str}/{full_str}"
            else:
                res = ""
        except OverflowError:
            res = ""
        em = discord.Embed(color=discord.Color.orange(), title=f"Paused")
        em.set_author(name=ctx.author, icon_url=ctx.author.display_avatar)
        em.description = f"[{song.title}]({song.uri}) {res}"
        await ctx.send(embed=em, view=utils.MusicView(bot=self.bot))

    @commands.hybrid_command()
    async def resume(self, ctx: commands.Context):
        """Resumes the player"""
        player = self.get_player(ctx.guild)
        if not player.paused:
            raise commands.CommandInvokeError("I'm not paused")
        song = player.current
        if song is None:
            raise commands.CommandInvokeError("I'm not playing anything")
        try:
            if song is not None:
                current_str = datetime.timedelta(seconds=int((player.position) / 1000))
                full_str = datetime.timedelta(seconds=int(song.duration / 1000))
                res = f"{current_str}/{full_str}"
            else:
                res = ""
        except OverflowError:
            res = ""
        em = discord.Embed(color=discord.Color.orange(), title=f"Resumed")
        em.set_author(name=ctx.author, icon_url=ctx.author.display_avatar)
        em.description = f"[{song.title}]({song.uri}) {res}"
        await ctx.send(embed=em, view=utils.MusicView(bot=self.bot))

    @commands.hybrid_command()
    async def skip(self, ctx: commands.Context):
        """Skips the current song"""
        player = self.get_player(ctx.guild)
        await player.play()
        player = self.get_player(ctx.guild)
        song = player.current
        if song is None:
            raise commands.CommandInvokeError("Nothing left to play")
        try:
            if song is not None:
                current_str = datetime.timedelta(seconds=int((player.position) / 1000))
                full_str = datetime.timedelta(seconds=int(song.duration / 1000))
                res = f"{current_str}/{full_str}"
            else:
                res = ""
        except OverflowError:
            res = ""
        em = discord.Embed(color=discord.Color.orange(), title=f"Skipped")
        em.set_author(name=ctx.author, icon_url=ctx.author.display_avatar)
        em.description = f"[{song.title}]({song.uri}) {res}"
        await ctx.send(embed=em, view=utils.MusicView(bot=self.bot))

    @commands.hybrid_command(aliases=["np"])
    async def nowplaying(self, ctx: commands.Context):
        """Shows the current playing song"""
        player = self.get_player(ctx.guild)
        song = player.current
        if song is None:
            raise commands.CommandInvokeError("I'm not playing anything")
        try:
            if song is not None:
                current_str = datetime.timedelta(seconds=int((player.position) / 1000))
                full_str = datetime.timedelta(seconds=int(song.duration / 1000))
                res = f"{current_str}/{full_str}"
            else:
                res = ""
        except OverflowError:
            res = ""
        em = discord.Embed(color=discord.Color.orange(), title=f"Now playing")
        em.set_author(name=ctx.author, icon_url=ctx.author.display_avatar)
        em.description = f"[{song.title}]({song.uri}) {res}"
        await ctx.send(embed=em, view=utils.MusicView(bot=self.bot))

    @commands.hybrid_command()
    async def queue(self, ctx: commands.Context):
        """Returns a nice paginator with buttons for the queue"""
        player = self.get_player(ctx.guild)
        entries = [f"[{k.title}]({k.uri})" for k in player.queue]
        if not entries:
            raise commands.CommandInvokeError("There is nothing left in the queue")
        paginator = utils.SimplePages(entries, ctx=ctx)
        await paginator.start()

    @commands.hybrid_command()
    @app_commands.describe(position="Valid formats examples: hh:mm:ss mm:ss 5m 1h")
    async def seek(self, ctx: commands.Context, position: str):
        """Seeks the player to a given position"""
        _time = timeparse(position)
        if _time is None:
            if not position.isdigit():
                raise commands.BadArgument("Invalid position argument")
            _time = int(position)
        player = self.get_player(ctx.guild)
        pos = _time * 1000
        if not player.is_playing:
            raise commands.CommandInvokeError("I'm not playing in this server")
        if not player.current.is_seekable:
            raise commands.CommandInvokeError("This song isn't seekable")
        pos = pos if pos < player.current.duration else player.current.duration
        await player.seek(pos)
        song = player.current
        try:
            current_str = datetime.timedelta(seconds=int((pos) / 1000))
            full_str = datetime.timedelta(seconds=int(song.duration / 1000))
            res = f"{current_str}/{full_str}"
        except OverflowError:
            res = ""
        em = discord.Embed(color=discord.Color.orange(), title="Seeked")
        em.set_author(name=ctx.author, icon_url=ctx.author.display_avatar)
        em.description = f"[{song.title}]({song.uri}) {res}"
        await ctx.send(embed=em, view=utils.MusicView(bot=self.bot))




    @commands.hybrid_command()
    @app_commands.describe(_type="The loop type")
    @app_commands.rename(_type="type")
    async def loop(
        self,
        ctx: commands.Context,
        _type: typing.Literal["off", "current", "queue"] = None,
    ):
        """Sets the loop of the player"""
        player = self.get_player(ctx.guild)
        if _type is None:
            if player.loop == 0:
                _type = "queue"
            else:
                _type = "off"
        loop_types = {"off": 0, "current": 1, "queue": 2}
        player.set_loop(loop_types[_type])
        song = player.current
        if song is None:
            raise commands.CommandInvokeError("I'm not playing anything")
        try:
            if song is not None:
                current_str = datetime.timedelta(seconds=int((player.position) / 1000))
                full_str = datetime.timedelta(seconds=int(song.duration / 1000))
                res = f"{current_str}/{full_str}"
            else:
                res = ""
        except OverflowError:
            res = ""
        em = discord.Embed(color=discord.Color.orange(), title=f"Set loop to {_type}")
        em.set_author(name=ctx.author, icon_url=ctx.author.display_avatar)
        em.description = f"[{song.title}]({song.uri}) {res}"
        await ctx.send(embed=em, view=utils.MusicView(bot=self.bot))


async def setup(bot: bot.AndreiBot):
    await bot.add_cog(Music(bot))