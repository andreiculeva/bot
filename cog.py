import discord
from discord.ext import commands
from discord import app_commands


class cog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def test(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "niggas you're fucked I can use my bot but it's not in the server"
        )

    @app_commands.command()
    @app_commands.allowed_installs(guilds=False,users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def perms(self, interaction:discord.Interaction):
        await interaction.response.send_message(f"roles: {interaction.guild.roles}", ephemeral=True)
    
    

async def setup(bot):
    await bot.add_cog(cog(bot))