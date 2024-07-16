from typing_extensions import Self
import random
import discord
from discord.ext import commands, menus
import re
import asyncio
import datetime
import copy
import typing
import utils
from humanfriendly import format_timespan
import bot
from discord import app_commands

allowed_guilds = (749670809110315019, 831556458398089217)




red = discord.Color.red()
orange = discord.Color.orange()


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


class Fun(commands.Cog):
    """Useless commands"""

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(name="\N{GAME DIE}")

    def __init__(self, bot: bot.AndreiBot) -> None:
        super().__init__()
        self.bot = bot

    @commands.hybrid_command()
    @discord.app_commands.describe(word="The words to search for")
    async def urban(self, ctx: commands.Context, *, word: str):
        """Searches urban dictionary."""

        url = "http://api.urbandictionary.com/v0/define"

        async with self.bot.session.get(url, params={"term": word}) as resp:
            if resp.status != 200:
                return await ctx.send(f"An error occurred: {resp.status} {resp.reason}")

            js = await resp.json()
            data = js.get("list", [])
            if not data:
                return await ctx.send("No results found, sorry.")

        pages = utils.RoboPages(UrbanDictionaryPageSource(data), ctx=ctx)
        await pages.start()



    @commands.command()
    async def c4(self, ctx: commands.Context, target: utils.MemberConverter):
        """Play connect 4 in the chat with someone"""
        PLAYER = ctx.message.author
        YES_EMOJI = "✅"
        NO_EMOJI = "❌"
        NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣"]
        RED = "🔴"
        BLUE = "🔵"
        BLACK = "⚫"
        GREEN = "🟢"

        if (target is None) and (ctx.message.reference is not None):
            player2 = (
                await ctx.message.channel.fetch_message(
                    ctx.message.reference.message_id
                )
            ).author
        else:
            player2 = target
            player1 = ctx.message.author
            if player2 == player1:
                await ctx.send("why do you want to play with yourself")
                return
            GAMEBOARD = [[0] * 6 for _ in range(7)]
            GAMEBOARD.reverse()
            invite_message = await ctx.send(
                f"<@{player2.id}> {player1.name} invited you to a c4 game, react to accept"
            )

            await invite_message.add_reaction(YES_EMOJI)
            await invite_message.add_reaction(NO_EMOJI)

            def check(reaction, user):
                if user == player2 and reaction.message == invite_message:
                    if str(reaction.emoji) == YES_EMOJI:
                        return True
                    elif str(reaction.emoji) == NO_EMOJI:
                        return True

            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add", check=check, timeout=60
                )
            except asyncio.TimeoutError:
                await ctx.send(f"{player2.name} didn't react", delete_after=10)
                await invite_message.delete(delay=10)
                return
            if str(reaction.emoji) == YES_EMOJI:
                await invite_message.delete()
            elif str(reaction.emoji) == NO_EMOJI:
                await ctx.send(
                    f"{player2.name} didn't accept your game", delete_after=10
                )
                await invite_message.delete(delay=10)
                return

            choices = copy.deepcopy(NUMS)

            def get_board_str(board):
                """takes the board with numbers and returns a string with colored balls"""
                temp_board = copy.deepcopy(board)
                for ls in temp_board:
                    for n, i in enumerate(ls):
                        if i == 0:
                            ls[n] = BLACK
                        elif i == 1:
                            ls[n] = RED
                        elif i == 2:
                            ls[n] = BLUE
                        elif i == 3:
                            ls[n] = GREEN
                return (
                    "\n".join(
                        [
                            "  ".join([str(temp_board[x][y]) for x in range(7)])
                            for y in range(6)
                        ]
                    )
                    + "\n"
                    + "  ".join(K for K in NUMS)
                )

            def play(choice, turn):
                """changes the value of the column in the board"""
                col = GAMEBOARD[choice]
                i = -1
                while col[i] != 0:
                    i -= 1
                col[i] = turn

            def get_winner(board, turn):
                """checks if there's a winner"""
                for row in range(6):
                    for col in range(4):
                        if (
                            board[col][row] == turn
                            and board[col + 1][row] == turn
                            and board[col + 2][row] == turn
                            and board[col + 3][row] == turn
                        ):
                            board[col][row] = GREEN
                            board[col + 1][row] = GREEN
                            board[col + 2][row] = GREEN
                            board[col + 3][row] = GREEN
                            return turn
                for col in board:
                    for row in range(3):
                        if (
                            col[row] == turn
                            and col[row + 1] == turn
                            and col[row + 2] == turn
                            and col[row + 3] == turn
                        ):
                            col[row] = GREEN
                            col[row + 1] = GREEN
                            col[row + 2] = GREEN
                            col[row + 3] = GREEN
                            return turn
                for col in range(4):
                    for i in range(3):
                        if (
                            board[col][i] == turn
                            and board[col + 1][i + 1] == turn
                            and board[col + 2][i + 2] == turn
                            and board[col + 3][i + 3] == turn
                        ):
                            board[col][i] = GREEN
                            board[col + 1][i + 1] = GREEN
                            board[col + 2][i + 2] = GREEN
                            board[col + 3][i + 3] = GREEN
                            return turn

                for col in range(3, 7):
                    for i in range(3):
                        if (
                            board[col][i] == turn
                            and board[col - 1][i + 1] == turn
                            and board[col - 2][i + 2] == turn
                            and board[col - 3][i + 3] == turn
                        ):
                            board[col][i] = GREEN
                            board[col - 1][i + 1] = GREEN
                            board[col - 2][i + 2] = GREEN
                            board[col - 3][i + 3] = GREEN
                            return turn

            title = f"CONNECT 4 GAME:\n{player1.name} vs {player2.name}"
            em = discord.Embed(title=title, description=get_board_str(GAMEBOARD))

            game_message = await ctx.send(embed=em)

            for emoji in NUMS:
                await game_message.add_reaction(emoji)
            await game_message.add_reaction(NO_EMOJI)

            for i in range(1000):
                if i % 2 == 0:
                    player = player1
                    p2 = player2
                    turn = 1
                    color = RED
                else:
                    player = player2
                    p2 = player1
                    turn = 2
                    color = BLUE

                status = f"{color}  {player}'s turn"
                em.set_footer(text=status)
                await game_message.edit(embed=em)

                def check(reaction, user):
                    if reaction.message == game_message:
                        if (
                            user.guild_permissions.administrator
                            and user != self.bot.user
                        ) and str(reaction.emoji) == NO_EMOJI:
                            return True
                        elif (
                            reaction.message == game_message
                            and user == player
                            and str(reaction.emoji) in choices
                        ):
                            return True
                        elif (user == player1 or user == player2) and str(
                            reaction.emoji
                        ) == NO_EMOJI:
                            return True
                        else:
                            return False

                try:
                    reaction, user = await self.bot.wait_for(
                        "reaction_add", check=check, timeout=180
                    )
                except asyncio.TimeoutError:
                    try:
                        em.set_footer(text=f"{player.name} didn't react, game ended")
                        await game_message.edit(embed=em)
                        game_msg = await ctx.message.channel.fetch_message(
                            game_message.id
                        )
                        await game_msg.clear_reactions()
                    except:
                        pass
                    return

                if str(reaction.emoji) == NO_EMOJI and user == p2:
                    em.set_footer(text=f"{p2} gave up")
                    await game_message.edit(embed=em)
                    try:
                        game_msg = await ctx.message.channel.fetch_message(
                            game_message.id
                        )
                        await game_msg.clear_reactions()
                    except:
                        pass
                    return

                elif str(reaction.emoji) == NO_EMOJI and (
                    (user != player1 and user != player2 and user != self.bot.user)
                    and user.guild_permissions.administrator
                ):
                    em.set_footer(text=f"game ended by an admin {user}")
                    await game_message.edit(embed=em)
                    try:
                        game_msg = await ctx.message.channel.fetch_message(
                            game_message.id
                        )
                        await game_msg.clear_reactions()
                    except:
                        pass
                    return

                elif str(reaction.emoji) == NO_EMOJI and user == player:
                    em.set_footer(text=f"{player} gave up")
                    await game_message.edit(embed=em)
                    try:
                        game_msg = await ctx.message.channel.fetch_message(
                            game_message.id
                        )
                        await game_msg.clear_reactions()
                    except:
                        pass
                    return

                else:
                    choice = NUMS.index(str(reaction.emoji))

                try:
                    game_msg = await ctx.message.channel.fetch_message(game_message.id)
                except:
                    em = discord.Embed(
                        title=title, description=get_board_str(GAMEBOARD)
                    )
                    em.set_footer(text=status)
                    game_message = await ctx.send(embed=em)
                    for n in choices:
                        await game_message.add_reaction(n)

                for r in game_msg.reactions:
                    rusers = [user async for user in r.users()]
                    for u in rusers:
                        if u != self.bot.user:
                            await r.remove(u)

                play(choice, turn)

                desc = get_board_str(GAMEBOARD)

                em = discord.Embed(title=title, description=desc)
                em.set_footer(text=status)
                await game_message.edit(embed=em)

                if GAMEBOARD[choice][0] != 0:
                    await game_msg.remove_reaction(NUMS[choice], self.bot.user)
                    choices.remove(NUMS[choice])

                w = get_winner(GAMEBOARD, turn)
                if w:
                    if w == 1:
                        w = player1
                    elif w == 2:
                        w = player2

                    winning_text = f"{color}  {w} won!"

                    em = discord.Embed(title=title, description=desc)
                    em.set_footer(text=winning_text)

                    await game_message.edit(embed=em)
                    await game_msg.clear_reactions()
                    em = discord.Embed(
                        title=title, description=get_board_str(GAMEBOARD)
                    )
                    em.set_footer(text=winning_text)
                    await asyncio.sleep(2)
                    await game_message.edit(embed=em)
                    return

                elif not any(0 in ls for ls in GAMEBOARD):
                    em = discord.Embed(
                        title=title, description=get_board_str(GAMEBOARD)
                    )
                    em.set_footer(text="TIE")
                    await game_message.edit(embed=em)
                    await game_msg.clear_reactions()
                    return

    async def chimpleaderboard(
        self, channel: discord.TextChannel, author: discord.User, bot: bot.AndreiBot
    ):
        # finish vvvvv
        data = await self.bot.pool.fetch("SELECT * FROM chimps")
        records: dict[int, tuple[int, datetime.timedelta]] = {
            x["user_id"]: (x["score"], format_timespan(x["play_time"].total_seconds()))
            for x in sorted(data, key=lambda k: k[1], reverse=True)
        }
        embed = discord.Embed(color=discord.Color.orange(), title="Chimp leaderboard")
        embed.set_author(name=author, icon_url=author.display_avatar)
        s = "\n".join(
            [
                f"{index+1}. {f'{bot.get_user(x[0])} {x[1][0]} ({x[1][1] if x[1][1] else 0})' if x[0]!=author.id else f'**{bot.get_user(x[0])} {x[1][0]} ({x[1][1] if x[1][1] else 0})**'}"
                for index, x in enumerate(records.items())
            ][:10]
        )
        s = (
            s.replace("1.", "\U0001f947")
            .replace("2.", "\U0001f948")
            .replace("3.", "\U0001f949")
        )
        if not (str(author) in s):
            d = records.get(author.id, (0, 0))
            if d:
                s += f"\n\n**{author}**: {d[0]} ({d[1]}s)"
        embed.description = s
        await channel.send(embed=embed)

    @commands.group(invoke_without_command=True)
    async def chimp(self, ctx: commands.Context, amount: int = 5):
        """Play the chimp game"""
        if amount > 25:
            amount = 25
        view = utils.ChimpView(amount, author=ctx.author, bot=self.bot)
        view.m = await ctx.send(
            view=view,
            content="Memorize the numbers on the grid and tap on the first one to start the game",
        )

    @chimp.command(aliases=["lb"])
    async def leaderboard(self, ctx: commands.Context):
        """Pulls out the leaderboard"""
        await self.chimpleaderboard(ctx.channel, ctx.author, self.bot)

    @commands.Cog.listener("on_raw_reaction_add")
    async def chimp_leaderboard_check(self, payload: discord.RawReactionActionEvent):
        """Pulls out the leaderboard as well"""
        if payload.user_id == self.bot.user.id:
            return
        if str(payload.emoji) != "\U0001f3c5":
            return
        channel = self.bot.get_channel(payload.channel_id)
        author = payload.member
        message = await channel.fetch_message(payload.message_id)
        if message.author != self.bot.user:
            return
        await self.chimpleaderboard(channel, author, self.bot)

    @commands.command()
    async def suggest(self, ctx: commands.Context[bot.AndreiBot], *, suggestion: str):
        """This command can be used to suggest new bot features or edits to the existing ones"""
        suggestions = ctx.bot.get_channel(999321557476311090)
        embed = discord.Embed(color=discord.Color.orange(), description=suggestion)
        embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar)
        embed.set_footer(text=f"ID: {ctx.author.id}")
        await suggestions.send(embed=embed)
        await ctx.message.add_reaction("\U0001f44d")

    @commands.hybrid_command(aliases=["msg"])
    @discord.app_commands.describe(
        user="The message will look like he sent it", content="the message's content"
    )
    @discord.app_commands.default_permissions(manage_messages=True)
    async def fakemessage(
        self,
        ctx: commands.Context,
        user: typing.Annotated[discord.User, utils.CustomUserTransformer],
        *,
        content: str,
    ):
        """Sends a fake message in the chat"""
        if not ctx.author.guild_permissions.manage_messages:
            return await ctx.send(
                "You need the `manage messages` permissions", ephemeral=True
            )
        if ctx.interaction:
            await ctx.defer(ephemeral=True)

        user = ctx.guild.get_member(user.id) or user

        webhook = None
        for _webhook in await ctx.channel.webhooks():
            if _webhook.token:
                webhook = _webhook
                break
        if webhook is None:
            webhook = await ctx.channel.create_webhook(name=str(ctx.bot))
        await webhook.send(
            username=user.display_name,
            avatar_url=user.display_avatar,
            content=content,
            allowed_mentions=discord.AllowedMentions(everyone=False),
        )
        if ctx.interaction:
            await ctx.send("done", ephemeral=True)
        else:
            await ctx.message.delete()





    @commands.command()
    async def slidepuzzle(self, ctx: commands.Context, number: int = 3):
        """Credit to z03h#6375 for this idea"""
        if number < 2:
            number = 2
        if number > 5:
            number = 5
        view = SlidePuzzle(ctx.author, number)
        view.mes = await ctx.send(
            content="Move the numbers in the correct order", view=view
        )


class SlidePuzzleButton(discord.ui.Button):
    def __init__(self, x: int, y: int, value: int = 0):
        super().__init__(style=discord.ButtonStyle.gray)
        self.value = value
        self.x = x
        self.y = y
        self.label = str(self.value) if self.value else utils.invis_character
        self.row = y - 1
        self.view: SlidePuzzle

    @property
    def win(self) -> bool:
        return self.view.correct_values == self.view.coordinates

    def new_move(self) -> Self:
        for children in self.view.children:
            if children.value != 0:
                continue
            if children.x == self.x - 1 and children.y == self.y:  # case on the left
                return children
            elif children.x == self.x + 1 and children.y == self.y:  # case on the right
                return children
            elif children.x == self.x and children.y == self.y + 1:  # case under it
                return children
            elif children.x == self.x and children.y == self.y - 1:  # case above it
                return children
        return None

    async def callback(self, interaction: discord.Interaction):
        move = self.new_move()
        if not move:
            return await interaction.response.defer()

        self.view.moves += 1
        if self.view.start is None:
            self.view.start = discord.utils.utcnow()

        self.view.coordinates[(move.x, move.y)] = self.value
        self.view.coordinates[(self.x, self.y)] = move.value
        self.view.clear_items()
        remaining = self.view.coordinates.copy()
        current = (1, 1)
        for _ in range(self.view.size * self.view.size):
            for coords, value in remaining.items():
                if coords != current:
                    continue
                x, y = coords
                self.view.add_item(SlidePuzzleButton(x, y, value))
                remaining.pop(coords)
                current_x, current_y = current
                if current_x == self.view.size:
                    current_x = 1
                    current_y += 1
                else:
                    current_x += 1
                current = (current_x, current_y)
                break

        self.view.validate_buttons()

        mes = f"Current moves: {self.view.moves}, you started {discord.utils.format_dt(self.view.start, 'R')}"
        if self.win:
            for button in self.view.children:
                button.disabled = True
            self.view.stop()
            seconds = int((discord.utils.utcnow() - self.view.start).total_seconds())
            _time = format_timespan(seconds, max_units=2, detailed=False)

            mes = f"It took you {self.view.moves} moves in {_time} to complete this"

        await interaction.response.edit_message(content=mes, view=self.view)


class SlidePuzzle(discord.ui.View):
    def __init__(self, author: discord.Member, number: int = 3) -> None:
        super().__init__(timeout=600)
        self.author = author
        self.size: typing.Literal[2, 3, 4, 5] = number
        self.coordinates: dict[tuple[int, int], int] = {}
        self.correct_values: dict[tuple[int, int], int] = {}
        self.moves = 0
        self.start: datetime.datetime = None
        current = 1
        for x in range(1, self.size + 1):
            for y in range(1, self.size + 1):
                button = SlidePuzzleButton(x, y)
                self.add_item(button)
                if current == (self.size * self.size):
                    current = 0
                self.correct_values[(y, x)] = current
                current += 1
        n = self.children
        random.shuffle(n)
        for number in range(1, (self.size * self.size)):
            button: SlidePuzzleButton = n[number - 1]
            button.value = number
            button.label = str(button.value) if button.value else utils.invis_character
            self.coordinates[(button.x, button.y)] = number
        self.validate_buttons()
        self.mes: discord.Message = None

    def validate_buttons(self) -> None:
        zero_button = None
        for button in self.children:
            button.disabled = True
            button.label = str(button.value) if button.value else utils.invis_character
            if self.correct_values[(button.x, button.y)] == button.value:
                if button.value != 0:
                    button.style = discord.ButtonStyle.green
            if button.value == 0:
                zero_button = button
        for children in self.children:
            if (
                children.x == zero_button.x - 1 and children.y == zero_button.y
            ):  # case on the left
                children.disabled = False
            elif (
                children.x == zero_button.x + 1 and children.y == zero_button.y
            ):  # case on the right
                children.disabled = False
            elif (
                children.x == zero_button.x and children.y == zero_button.y + 1
            ):  # case under it
                children.disabled = False
            elif (
                children.x == zero_button.x and children.y == zero_button.y - 1
            ):  # case above it
                children.disabled = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.author == interaction.user:
            return True
        await interaction.response.send_message(
            f"This game is for {self.author.mention}", ephemeral=True
        )

    async def on_timeout(self) -> None:
        self.stop()
        for button in self.children:
            button.disabled = True
        await self.mes.edit(view=self, content="You got timed out")


async def setup(bot: bot.AndreiBot):
    await bot.add_cog(Fun(bot))
