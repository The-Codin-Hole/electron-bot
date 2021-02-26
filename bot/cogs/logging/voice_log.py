from discord import Color, Embed, Guild, Member, VoiceState
from discord.ext.commands import Cog

from bot.core.bot import Bot
from bot.database.log_channels import LogChannels


class MessageLog(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    async def send_log(self, guild: Guild, *send_args, **send_kwargs) -> bool:
        """
        Try to send a log message to a voice_log channel for given guild,
        args and kwargs to this function will be used in the actual `Channel.send` call.

        If the message was sent, return True, otherwise return False
        (might happen if voice_log channel isn't defined in database).
        """
        mod_log_id = await LogChannels.get_log_channel(self.bot.db_engine, "voice_log", guild)
        mod_log_channel = guild.get_channel(mod_log_id)
        if mod_log_channel is None:
            return False

        await mod_log_channel.send(*send_args, **send_kwargs)
        return True

    @Cog.listener()
    async def on_voice_state_update(self, member: Member, before: VoiceState, after: VoiceState) -> None:
        if before.afk != after.afk:
            embed = Embed(
                title="User went AFK" if after.afk else "User is no longer AFK",
                description=f"**User:** {member.mention}",
                color=Color.blue()
            )
        elif before.channel != after.channel:
            embed = Embed(
                title="User changed channels" if after.channel else "User left voice channel",
                description=f"**User:** {member.mention}"
                            f"\n**Channel:** {before.channel}"
                            f"\n**New Channel:** {after.channel}" if after.channel else "",
                color=Color.blue()
            )
        elif before.deaf != after.deaf:
            embed = Embed(
                title="User deafened" if after.deaf else "User undeafened",
                description=f"**User:** {member.mention}",
                color=Color.dark_orange()
            )
        elif before.mute != after.mute:
            embed = Embed(
                title="User silenced" if after.mute else "User unsilenced",
                description=f"**User:** {member.mention}",
                color=Color.dark_orange()
            )
        # Client actions cal also happen here, i.e. self mute/deaf/stream/video
        # we don't need to log those, so we can return early in that case
        else:
            return

        embed.set_thumbnail(url=member.avatar_url)

        await self.send_log(member.guild, embed=embed)


def setup(bot: Bot) -> None:
    bot.add_cog(MessageLog(bot))
