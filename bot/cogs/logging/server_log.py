import datetime
import typing as t

from discord import (
    CategoryChannel, Color, Embed, Guild,
    Role, TextChannel, VoiceChannel
)
from discord.abc import GuildChannel
from discord.ext.commands import Cog

from bot.core.bot import Bot
from bot.database.log_channels import LogChannels
from bot.utils.time import stringify_duration


class ServerLog(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    async def send_log(self, guild: Guild, *send_args, **send_kwargs) -> bool:
        """
        Try to send a log message to a server_log channel for given guild,
        args and kwargs to this function will be used in the actual `Channel.send` call.

        If the message was sent, return True, otherwise return False
        (might happen if server_log channel isn't defined in database).
        """
        server_log_id = await LogChannels.get_log_channel(self.bot.db_engine, "server_log", guild)
        server_log_channel = guild.get_channel(int(server_log_id))
        if server_log_channel is None:
            return False

        await server_log_channel.send(*send_args, **send_kwargs)
        return True

    # region: Channels

    @classmethod
    def make_channel_update_embed(cls, channel_before: GuildChannel, channel_after: GuildChannel) -> t.Optional[Embed]:
        embed = None

        if channel_before.overwrites != channel_after.overwrites:
            embed = cls._channel_permissions_diff_embed(channel_before, channel_after)

        if isinstance(channel_before, TextChannel) and embed is None:
            slowmode_readable = lambda time: stringify_duration(time) if time != 0 else None
            embed = cls._specific_channel_update_embed(
                channel_before, channel_after,
                title="Text Channel updated",
                check_params={
                    "name": "Name",
                    "topic": "Topic",
                    "is_nsfw": (lambda is_nsfw_func: is_nsfw_func(), "NSFW"),
                    "slowmode_delay": (slowmode_readable, "Slowmode delay"),
                    "category": "Category",
                }
            )
        if isinstance(channel_before, VoiceChannel) and embed is None:
            readable_bitrate = lambda bps: f"{round(bps/1000)}kbps"
            embed = cls._specific_channel_update_embed(
                channel_before, channel_after,
                title="Voice Channel updated",
                check_params={
                    "name": "Name",
                    "bitrate": (readable_bitrate, "Bitrate"),
                    "user_limit": "User limit",
                    "category": "Category",
                }
            )
        if isinstance(channel_before, CategoryChannel) and embed is None:
            embed = cls._specific_channel_update_embed(
                channel_before, channel_after,
                title="Category Channel updated",
                check_params={
                    "name": "Name",
                    "is_nsfw": "NSFW",
                }
            )

        if embed is not None:
            embed.timestamp = datetime.datetime.now()

        return embed

    @staticmethod
    def _specific_channel_update_embed(
        channel_before: GuildChannel,
        channel_after: GuildChannel,
        title: str,
        check_params: dict
    ) -> t.Optional[Embed]:
        """
        Generate embed for difference between 2 passed channels.

        `check_params` is a dictionary which defines what variables should
        be compared.
        Keys should always be strings, referring to variable names.
        Values are either:
            * string: readable description of the update variable
            * tuple (callable, string): callable is ran which on obtained values for better readability
        """
        embed = Embed(
            title=title,
            description=f"**Channel:** {channel_after.mention}",
            color=Color.dark_blue()
        )

        field_before_text = []
        field_after_text = []

        for parameter_name, value in check_params.items():
            before_param = getattr(channel_before, parameter_name)
            after_param = getattr(channel_after, parameter_name)
            if isinstance(value, tuple):
                func = value[0]
                before_param = func(before_param)
                after_param = func(after_param)
                # Continue with 2nd element (should be parameter name string)
                value = value[1]

            if before_param != after_param:
                field_before_text.append(f"**{value}:** {before_param}")
                field_after_text.append(f"**{value}:** {after_param}")

        if len(field_after_text) == 0:
            return

        embed.add_field(
            name="Before",
            value="\n".join(field_before_text),
            inline=True
        )
        embed.add_field(
            name="After",
            value="\n".join(field_after_text),
            inline=True
        )

        return embed

    @staticmethod
    def _channel_permissions_diff_embed(channel_before: GuildChannel, channel_after: GuildChannel) -> t.Optional[Embed]:
        if isinstance(channel_before, TextChannel):
            channel_type = "Text channel"
        elif isinstance(channel_before, VoiceChannel):
            channel_type = "Voice channel"
        elif isinstance(channel_before, CategoryChannel):
            channel_type = "Category channel"

        embed_lines = []
        all_overwrites = set(channel_before.overwrites.keys()).union(set(channel_after.overwrites.keys()))

        for overwrite_for in all_overwrites:
            before_overwrites = channel_before.overwrites_for(overwrite_for)
            after_overwrites = channel_after.overwrites_for(overwrite_for)

            if before_overwrites == after_overwrites:
                continue

            embed_lines.append(f"**Overwrite changes for {overwrite_for.mention}:**")

            for before_perm, after_perm in zip(before_overwrites, after_overwrites):
                if before_perm[1] != after_perm[1]:
                    perm_name = before_perm[0].replace("_", " ").capitalize()

                    if before_perm[1] is True:
                        before_emoji = "✅"
                    elif before_perm[1] is False:
                        before_emoji = "❌"
                    else:
                        before_emoji = "⬜"

                    if after_perm[1] is True:
                        after_emoji = "✅"
                    elif after_perm[1] is False:
                        after_emoji = "❌"
                    else:
                        after_emoji = "⬜"

                    embed_lines.append(f"**`{perm_name}:`** {before_emoji} ➜ {after_emoji}")

        # Don't send an embed without permissions edited,
        # it only means that an override was added, but it's
        # staying with all permissions at `None`
        if len(embed_lines) == 0:
            return

        embed_text = f"{channel_after.mention} permissions have been updated.\n\n"
        embed_text += "\n".join(embed_lines)

        permissions_embed = Embed(
            title=f"{channel_type} permissions updated",
            description=embed_text,
            color=Color.dark_blue()
        )

        return permissions_embed

    @Cog.listener()
    async def on_guild_channel_update(self, channel_before: GuildChannel, channel_after: GuildChannel) -> None:
        embed = self.make_channel_update_embed(channel_before, channel_after)
        if embed is None:
            return

        await self.send_log(channel_after.guild, embed=embed)

    @Cog.listener()
    async def on_guild_channel_delete(self, channel: GuildChannel) -> None:
        # TODO: Finish this
        pass

    @Cog.listener()
    async def on_guild_channel_create(self, channel: GuildChannel) -> None:
        # TODO: Finish this
        pass

    # endregion
    # region: Roles

    @Cog.listener()
    async def on_guild_role_create(self, role: Role) -> None:
        # TODO: Finish this
        pass

    @Cog.listener()
    async def on_guild_role_delete(self, role: Role) -> None:
        # TODO: Finish this
        pass

    @Cog.listener()
    async def on_guild_role_update(self, before: Role, after: Role) -> None:
        # TODO: Finish this
        pass

    # endregion

    @Cog.listener()
    async def on_guild_update(self, before: Guild, after: Guild) -> None:
        # TODO: Finish this
        pass


def setup(bot: Bot) -> None:
    bot.add_cog(ServerLog(bot))
