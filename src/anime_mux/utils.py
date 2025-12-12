"""Shared utilities, constants, and console setup."""

from rich.console import Console

# Singleton console for consistent output
console = Console()

# Supported file extensions
VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".webm"}
AUDIO_EXTENSIONS = {".mka", ".aac", ".ac3", ".flac", ".mp3", ".opus", ".m4a", ".dts"}
SUBTITLE_EXTENSIONS = {".srt", ".ass", ".ssa", ".vtt", ".sub", ".idx"}

# Keywords for directory discovery
AUDIO_DIR_KEYWORDS = {
    "sound",
    "audio",
    "voiceover",
    "voice",
    "dub",
    "sounds",
    "voiceovers",
}
SUBTITLE_DIR_KEYWORDS = {"subtitle", "sub", "subs", "caption", "subtitles"}

# Exact directory names to search for
AUDIO_SEARCH_DIRS = ["Sounds", "Audio", "Voiceovers", "Sound", "Voiceover"]
SUBTITLE_SEARCH_DIRS = ["Subtitles", "Subs", "Sub"]
