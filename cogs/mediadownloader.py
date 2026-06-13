from __future__ import annotations

import asyncio
import io
import mimetypes
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
import discord
import yt_dlp

from discord import app_commands
from discord.ext import commands


class MediaDownloader(commands.Cog):
    """
    Generic media downloader Cog using yt-dlp.

    Commands:
        !download <url>
        !dl <url>
        /download url:<url>

    Message context menu:
        Right-click message -> Apps -> download media

    Requirements:
        pip install discord.py yt-dlp aiohttp

    System dependency:
        ffmpeg must be installed and available in PATH.
    """

    DEFAULT_UPLOAD_LIMIT_BYTES = 25 * 1024 * 1024
    DISCORD_MAX_FILES_PER_MESSAGE = 10
    MAX_URLS_PER_MESSAGE_COMMAND = 3

    URL_REGEX = re.compile(
        r"https?://[^\s<>\"]+",
        re.IGNORECASE,
    )

    VIDEO_SUFFIXES = {
        ".mp4",
        ".mov",
        ".mkv",
        ".webm",
        ".avi",
        ".m4v",
    }

    def __init__(
        self,
        bot: commands.Bot,
        *,
        concurrent_downloads: int = 2,
    ) -> None:
        super().__init__()
        self.bot = bot
        self.download_semaphore = asyncio.Semaphore(concurrent_downloads)

    # -------------------------------------------------------------------------
    # Cog load/unload
    # -------------------------------------------------------------------------

    async def cog_load(self) -> None:
        tree = self.bot.tree

        @app_commands.allowed_installs(
            guilds=True,
            users=True,
        )
        @app_commands.allowed_contexts(
            guilds=True,
            dms=True,
            private_channels=True,
        )
        @tree.context_menu(name="download media")
        async def download_media_context_menu(
            interaction: discord.Interaction,
            message: discord.Message,
        ):
            await self.handle_message_context_download(interaction, message)

        return await super().cog_load()

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(
            "download media",
            type=discord.AppCommandType.message,
        )

        return await super().cog_unload()

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def sanitize_filename(name: str) -> str:
        name = re.sub(r'[\\/*?:"<>|]', "_", name)
        name = re.sub(r"\s+", " ", name).strip()
        return name[:180] or "download"

    @staticmethod
    def bytes_to_mb(size: int) -> float:
        return size / 1024 / 1024

    @staticmethod
    def is_probably_url(value: str) -> bool:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    @staticmethod
    def is_probably_direct_image_url(url: str) -> bool:
        path = urlparse(url).path.lower()

        return path.endswith(
            (
                ".jpg",
                ".jpeg",
                ".png",
                ".gif",
                ".webp",
                ".bmp",
                ".tiff",
                ".avif",
            )
        )

    @classmethod
    def get_upload_limit_bytes(cls, ctx: commands.Context) -> int:
        if ctx.guild is not None:
            return ctx.guild.filesize_limit

        return cls.DEFAULT_UPLOAD_LIMIT_BYTES

    @classmethod
    def get_upload_limit_bytes_from_interaction(
        cls,
        interaction: discord.Interaction,
    ) -> int:
        if interaction.guild is not None:
            return interaction.guild.filesize_limit

        return cls.DEFAULT_UPLOAD_LIMIT_BYTES

    @classmethod
    def extract_urls_from_message(cls, message: discord.Message) -> list[str]:
        urls: list[str] = []

        for match in cls.URL_REGEX.findall(message.content or ""):
            cleaned = match.strip("<>")
            cleaned = cleaned.rstrip(".,;:!?)]}")

            if cleaned and cleaned not in urls:
                urls.append(cleaned)

        for attachment in message.attachments:
            if attachment.url and attachment.url not in urls:
                urls.append(attachment.url)

        return urls

    @staticmethod
    def find_downloaded_files(output_dir: Path) -> list[Path]:
        ignored_suffixes = {
            ".part",
            ".ytdl",
            ".temp",
            ".tmp",
        }

        files: list[Path] = []

        for path in output_dir.iterdir():
            if not path.is_file():
                continue

            if path.suffix.lower() in ignored_suffixes:
                continue

            files.append(path)

        files.sort(key=lambda p: p.stat().st_size, reverse=True)
        return files

    @staticmethod
    def format_exception(error: Exception, limit: int = 1500) -> str:
        text = str(error)

        if len(text) > limit:
            text = text[:limit] + "..."

        return text

    # -------------------------------------------------------------------------
    # Direct image downloader, fully in memory
    # -------------------------------------------------------------------------

    async def download_direct_image_to_memory(
        self,
        url: str,
        *,
        max_filesize_bytes: int,
    ) -> tuple[io.BytesIO, str]:
        timeout = aiohttp.ClientTimeout(
            total=None,
            sock_connect=30,
            sock_read=60,
        )

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                response.raise_for_status()

                content_length = response.headers.get("Content-Length")
                if content_length is not None:
                    expected_size = int(content_length)

                    if expected_size > max_filesize_bytes:
                        expected_mb = self.bytes_to_mb(expected_size)
                        limit_mb = self.bytes_to_mb(max_filesize_bytes)

                        raise ValueError(
                            f"That file is too large to upload here "
                            f"({expected_mb:.1f} MB > {limit_mb:.1f} MB)."
                        )

                content_type = response.headers.get("Content-Type", "")
                guessed_ext = mimetypes.guess_extension(
                    content_type.split(";")[0]
                )

                url_path = Path(urlparse(url).path)
                ext = url_path.suffix or guessed_ext or ".bin"

                filename = self.sanitize_filename(url_path.stem or "image") + ext

                buffer = io.BytesIO()
                downloaded = 0

                async for chunk in response.content.iter_chunked(1024 * 256):
                    downloaded += len(chunk)

                    if downloaded > max_filesize_bytes:
                        raise ValueError(
                            "That file became larger than this server's upload limit "
                            "while downloading."
                        )

                    buffer.write(chunk)

                buffer.seek(0)
                return buffer, filename

    # -------------------------------------------------------------------------
    # iOS-compatible MP4 conversion
    # -------------------------------------------------------------------------

    def make_ios_compatible_mp4(self, input_path: Path) -> Path:
        """
        Re-encode video into an iOS Photos-friendly MP4.

        Output:
            - MP4 container
            - H.264 video
            - AAC audio
            - yuv420p pixel format
            - faststart metadata
        """
        output_path = input_path.with_name(f"{input_path.stem}.ios.mp4")

        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),

            # Video
            "-map",
            "0:v:0",
            "-c:v",
            "libx264",
            "-profile:v",
            "high",
            "-level",
            "4.1",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "veryfast",
            "-crf",
            "23",

            # Optional audio
            "-map",
            "0:a?",
            "-c:a",
            "aac",
            "-b:a",
            "128k",

            # Better mobile/web playback
            "-movflags",
            "+faststart",

            str(output_path),
        ]

        subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        return output_path

    # -------------------------------------------------------------------------
    # yt-dlp downloader
    # -------------------------------------------------------------------------

    def download_with_ytdlp(
        self,
        url: str,
        output_dir: Path,
        *,
        max_filesize_bytes: int,
    ) -> list[Path]:
        """
        Blocking yt-dlp function.

        This is run inside asyncio.to_thread().
        """
        output_template = str(output_dir / "%(title).180s [%(id)s].%(ext)s")

        ydl_opts = {
            # Prefer H.264 video + AAC audio when possible.
            # This helps avoid VP9/AV1 MP4s that iOS Photos may refuse to save.
            "format": (
                "bv*[vcodec^=avc1][ext=mp4]+ba[acodec^=mp4a][ext=m4a]/"
                "bv*[vcodec^=avc1]+ba[acodec^=mp4a]/"
                "b[vcodec^=avc1][ext=mp4]/"
                "best[ext=mp4]/"
                "best"
            ),

            "outtmpl": output_template,

            # Merge separate streams into MP4 where possible.
            "merge_output_format": "mp4",

            # Prevent accidental playlist downloads.
            "noplaylist": True,

            # Avoid downloading files Discord cannot upload.
            "max_filesize": max_filesize_bytes,

            "quiet": True,
            "no_warnings": True,
            "continuedl": True,

            "writethumbnail": False,
            "writeinfojson": False,
            "writesubtitles": False,
            "writeautomaticsub": False,

            "ignoreerrors": False,
            "restrictfilenames": False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)

        downloaded_files = self.find_downloaded_files(output_dir)
        final_files: list[Path] = []

        for file_path in downloaded_files:
            if file_path.suffix.lower() not in self.VIDEO_SUFFIXES:
                final_files.append(file_path)
                continue

            try:
                ios_file = self.make_ios_compatible_mp4(file_path)
                final_files.append(ios_file)
            except subprocess.CalledProcessError as error:
                stderr = ""

                if error.stderr:
                    try:
                        stderr = error.stderr.decode(errors="replace")
                    except AttributeError:
                        stderr = str(error.stderr)

                raise RuntimeError(
                    "ffmpeg failed while converting the video to iOS-compatible MP4.\n"
                    f"{stderr[:1500]}"
                ) from error

        return final_files

    async def download_media_to_temp_folder(
        self,
        url: str,
        *,
        max_filesize_bytes: int,
    ) -> tuple[list[Path], Path]:
        """
        Downloads using yt-dlp into an OS temp folder.

        The caller must delete the returned temp folder.
        """
        temp_dir = Path(tempfile.mkdtemp(prefix="discord-ytdlp-"))

        try:
            files = await asyncio.to_thread(
                self.download_with_ytdlp,
                url,
                temp_dir,
                max_filesize_bytes=max_filesize_bytes,
            )

            return files, temp_dir

        except Exception:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise

    # -------------------------------------------------------------------------
    # Shared URL processor
    # -------------------------------------------------------------------------

    async def prepare_discord_files_from_url(
        self,
        url: str,
        *,
        upload_limit_bytes: int,
    ) -> tuple[list[discord.File], Path | None]:
        upload_limit_mb = self.bytes_to_mb(upload_limit_bytes)

        if not self.is_probably_url(url):
            raise ValueError("That does not look like a valid `http` or `https` URL.")

        # Direct image URLs are handled fully in memory.
        if self.is_probably_direct_image_url(url):
            image_buffer, filename = await self.download_direct_image_to_memory(
                url,
                max_filesize_bytes=upload_limit_bytes,
            )

            return [discord.File(image_buffer, filename=filename)], None

        # Everything else uses yt-dlp in an OS temp folder.
        files, temp_dir = await self.download_media_to_temp_folder(
            url,
            max_filesize_bytes=upload_limit_bytes,
        )

        if not files:
            raise ValueError("I could not find any downloadable media from that URL.")

        sendable_files: list[discord.File] = []

        for file_path in files:
            if not file_path.exists():
                continue

            size = file_path.stat().st_size

            if size > upload_limit_bytes:
                size_mb = self.bytes_to_mb(size)

                raise ValueError(
                    f"Downloaded `{file_path.name}`, but it is too large "
                    f"to upload here.\n"
                    f"File size: `{size_mb:.1f} MB`\n"
                    f"Upload limit here: `{upload_limit_mb:.1f} MB`"
                )

            sendable_files.append(
                discord.File(
                    file_path,
                    filename=file_path.name,
                )
            )

        if not sendable_files:
            raise ValueError(
                "The download finished, but I could not find a valid file to send."
            )

        return sendable_files[: self.DISCORD_MAX_FILES_PER_MESSAGE], temp_dir

    # -------------------------------------------------------------------------
    # Hybrid command
    # -------------------------------------------------------------------------

    @commands.hybrid_command(
        name="download",
        aliases=["dl"],
        description="Download media from a URL and send it here.",
    )
    async def download(
        self,
        ctx: commands.Context[commands.Bot],
        url: str = commands.parameter(
            description="The URL containing the video, image, or media."
        ),
    ):
        await ctx.defer()

        if ctx.interaction is None:
            await ctx.typing()

        upload_limit_bytes = self.get_upload_limit_bytes(ctx)

        temp_dir: Path | None = None

        async with self.download_semaphore:
            try:
                sendable_files, temp_dir = await self.prepare_discord_files_from_url(
                    url,
                    upload_limit_bytes=upload_limit_bytes,
                )

                await ctx.reply(files=sendable_files)

            except yt_dlp.utils.DownloadError as error:
                await ctx.reply(
                    "Could not download that URL.\n"
                    f"```text\n{self.format_exception(error)}\n```"
                )

            except aiohttp.ClientResponseError as error:
                await ctx.reply(
                    f"Direct image download failed with HTTP status `{error.status}`."
                )

            except ValueError as error:
                await ctx.reply(str(error))

            except Exception as error:
                await ctx.reply(
                    "Something went wrong while downloading that media.\n"
                    f"```text\n{self.format_exception(error)}\n```"
                )

            finally:
                if temp_dir is not None:
                    shutil.rmtree(temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Message context command handler
    # -------------------------------------------------------------------------

    async def handle_message_context_download(
        self,
        interaction: discord.Interaction,
        message: discord.Message,
    ) -> None:
        urls = self.extract_urls_from_message(message)

        if not urls:
            return await interaction.response.send_message(
                "I could not find any URLs or attachments in that message.",
                ephemeral=True,
            )

        limited_urls = urls[: self.MAX_URLS_PER_MESSAGE_COMMAND]
        skipped_count = max(0, len(urls) - len(limited_urls))

        await interaction.response.defer(thinking=True)

        upload_limit_bytes = self.get_upload_limit_bytes_from_interaction(interaction)

        if skipped_count:
            await interaction.followup.send(
                f"Found `{len(urls)}` URLs/attachments. "
                f"Downloading the first `{len(limited_urls)}` only."
            )

        for index, url in enumerate(limited_urls, start=1):
            temp_dir: Path | None = None

            async with self.download_semaphore:
                try:
                    sendable_files, temp_dir = await self.prepare_discord_files_from_url(
                        url,
                        upload_limit_bytes=upload_limit_bytes,
                    )

                    content = None
                    if len(limited_urls) > 1:
                        content = f"URL `{index}/{len(limited_urls)}`:"

                    await interaction.followup.send(
                        content=content,
                        files=sendable_files,
                    )

                except yt_dlp.utils.DownloadError as error:
                    await interaction.followup.send(
                        f"Could not download URL `{index}`.\n"
                        f"```text\n{self.format_exception(error)}\n```"
                    )

                except aiohttp.ClientResponseError as error:
                    await interaction.followup.send(
                        f"Direct image download failed for URL `{index}` "
                        f"with HTTP status `{error.status}`."
                    )

                except ValueError as error:
                    await interaction.followup.send(
                        f"Could not process URL `{index}`:\n{error}"
                    )

                except Exception as error:
                    await interaction.followup.send(
                        f"Something went wrong while downloading URL `{index}`.\n"
                        f"```text\n{self.format_exception(error)}\n```"
                    )

                finally:
                    if temp_dir is not None:
                        shutil.rmtree(temp_dir, ignore_errors=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(MediaDownloader(bot))