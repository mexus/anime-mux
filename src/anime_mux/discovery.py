"""Discovery of video files and external audio/subtitle sources."""

from pathlib import Path

from .matcher import extract_episode_numbers
from .models import ExternalSource, TrackType
from .utils import (
    AUDIO_DIR_KEYWORDS,
    AUDIO_EXTENSIONS,
    AUDIO_SEARCH_DIRS,
    SUBTITLE_DIR_KEYWORDS,
    SUBTITLE_EXTENSIONS,
    SUBTITLE_SEARCH_DIRS,
    VIDEO_EXTENSIONS,
    console,
)


def find_video_files(directory: Path) -> list[Path]:
    """Find video files in the top-level of a directory (non-recursive)."""
    files = []
    for f in directory.iterdir():
        if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
            files.append(f)
    return sorted(files)


def _find_files_with_extensions(
    directory: Path, extensions: set[str], recursive: bool = True
) -> list[Path]:
    """Find files with given extensions in a directory."""
    files: list[Path] = []
    if recursive:
        for ext in extensions:
            files.extend(directory.rglob(f"*{ext}"))
    else:
        for f in directory.iterdir():
            if f.is_file() and f.suffix.lower() in extensions:
                files.append(f)
    return sorted(files)


def _find_source_directories(
    base_dir: Path,
    search_dirs: list[str],
    keywords: set[str],
) -> list[Path]:
    """Find directories that might contain audio or subtitle sources."""
    potential_locations = {base_dir, base_dir.parent}
    found_paths: list[Path] = []

    for loc in potential_locations:
        if not loc.is_dir():
            continue

        # Check for exact names from search list
        for name in search_dirs:
            candidate = loc / name
            if candidate.is_dir():
                found_paths.append(candidate)

        # Check for any directory containing keywords
        try:
            for item in loc.iterdir():
                if item.is_dir():
                    name_lower = item.name.lower()
                    if any(kw in name_lower for kw in keywords):
                        found_paths.append(item)
        except PermissionError:
            pass

    # Remove duplicates while preserving order
    seen: set[Path] = set()
    unique_paths: list[Path] = []
    for path in found_paths:
        if path not in seen:
            seen.add(path)
            unique_paths.append(path)

    return unique_paths


def discover_audio_sources(
    base_dir: Path,
    override_dir: Path | None = None,
) -> dict[str, ExternalSource]:
    """
    Discover audio voiceover directories and map their files by episode number.

    Args:
        base_dir: Base directory to search from (typically video directory)
        override_dir: Optional explicit audio directory to use

    Returns:
        Dictionary mapping source name to ExternalSource
    """
    sources: dict[str, ExternalSource] = {}
    search_paths: list[Path] = []

    if override_dir:
        if not override_dir.is_dir():
            console.print(
                f"[yellow]Warning: Provided audio directory does not exist: {override_dir}[/yellow]"
            )
            return {}
        search_paths.append(override_dir)
    else:
        search_paths = _find_source_directories(
            base_dir, AUDIO_SEARCH_DIRS, AUDIO_DIR_KEYWORDS
        )

    if not search_paths:
        return {}

    for path in search_paths:
        # First, check if audio files exist directly in this directory
        direct_audio_files = _find_files_with_extensions(
            path, AUDIO_EXTENSIONS, recursive=True
        )
        files_in_subdirs = any(f.parent != path for f in direct_audio_files)

        if direct_audio_files and not files_in_subdirs:
            # Audio files are directly in this directory (flat structure)
            voiceover_name = path.name
            episode_map = extract_episode_numbers(direct_audio_files)
            if episode_map:
                sources[voiceover_name] = ExternalSource(
                    name=voiceover_name,
                    source_type=TrackType.AUDIO,
                    base_path=path,
                    files=episode_map,
                )
        else:
            # Look for subdirectories containing audio (nested structure)
            try:
                for subdir in path.iterdir():
                    if subdir.is_dir():
                        voiceover_name = subdir.name
                        audio_files = _find_files_with_extensions(
                            subdir, AUDIO_EXTENSIONS, recursive=True
                        )
                        if audio_files:
                            episode_map = extract_episode_numbers(audio_files)
                            if episode_map:
                                sources[voiceover_name] = ExternalSource(
                                    name=voiceover_name,
                                    source_type=TrackType.AUDIO,
                                    base_path=subdir,
                                    files=episode_map,
                                )
            except PermissionError:
                pass

    return sources


def discover_subtitle_sources(
    base_dir: Path,
    override_dir: Path | None = None,
) -> dict[str, ExternalSource]:
    """
    Discover subtitle directories and map their files by episode number.

    Args:
        base_dir: Base directory to search from (typically video directory)
        override_dir: Optional explicit subtitle directory to use

    Returns:
        Dictionary mapping source name to ExternalSource
    """
    sources: dict[str, ExternalSource] = {}
    search_paths: list[Path] = []

    if override_dir:
        if not override_dir.is_dir():
            console.print(
                f"[yellow]Warning: Provided subtitle directory does not exist: {override_dir}[/yellow]"
            )
            return {}
        search_paths.append(override_dir)
    else:
        search_paths = _find_source_directories(
            base_dir, SUBTITLE_SEARCH_DIRS, SUBTITLE_DIR_KEYWORDS
        )

    if not search_paths:
        return {}

    for root_sub_dir in search_paths:
        all_sub_files = _find_files_with_extensions(
            root_sub_dir, SUBTITLE_EXTENSIONS, recursive=True
        )

        # Group files by their parent directory
        files_by_dir: dict[Path, list[Path]] = {}
        for file_path in all_sub_files:
            parent_dir = file_path.parent
            if parent_dir not in files_by_dir:
                files_by_dir[parent_dir] = []
            files_by_dir[parent_dir].append(file_path)

        for sub_dir, files in files_by_dir.items():
            if not files:
                continue

            # Generate a descriptive name from the relative path
            try:
                relative_path = sub_dir.relative_to(root_sub_dir)
                if str(relative_path) == ".":
                    source_name = root_sub_dir.name
                else:
                    source_name = f"{root_sub_dir.name}/{relative_path}"
            except ValueError:
                source_name = sub_dir.name

            episode_map = extract_episode_numbers(files)
            if episode_map:
                # Handle duplicate source names
                final_name = source_name
                if final_name in sources:
                    final_name = f"{source_name} ({root_sub_dir.parent.name})"

                sources[final_name] = ExternalSource(
                    name=final_name,
                    source_type=TrackType.SUBTITLE,
                    base_path=sub_dir,
                    files=episode_map,
                )

    return sources
