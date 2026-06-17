"""Episode number extraction from filenames."""

import re
from pathlib import Path

from .constants import SPECIAL_EPISODE_PREFIXES

# Patterns for special episode markers (OVA, SP, etc.) with optional number suffix
# The number is optional - missing number implies episode 1
# Imported from constants: SPECIAL_EPISODE_PREFIXES


def _try_prefixed_pattern(files: list[Path]) -> dict[int, Path]:
    """
    Try to match prefixed episode patterns like OVA, OVA2, OVA3.

    These patterns have an alphabetic prefix followed by an optional number,
    where missing number implies episode 1.
    """
    for prefix in SPECIAL_EPISODE_PREFIXES:
        # Pattern: prefix followed by optional digits, case-insensitive
        # The prefix must be a word boundary (not part of a larger word)
        prefix_pattern = re.compile(
            rf"(?<![a-zA-Z])({re.escape(prefix)})(\d*)(?![a-zA-Z\d])",
            re.IGNORECASE,
        )

        # Find the prefix in first file to establish template
        template_name = files[0].name
        matches = list(prefix_pattern.finditer(template_name))

        for match in matches:
            # Build pattern with everything before and after the prefix+number
            before = template_name[: match.start()]
            after = template_name[match.end() :]

            # Create pattern: literal prefix + captured optional number
            pattern_str = (
                f"^{re.escape(before)}(?:{re.escape(prefix)})(\\d*){re.escape(after)}$"
            )
            pattern = re.compile(pattern_str, re.IGNORECASE)

            episode_map: dict[int, Path] = {}
            is_valid = True

            for file_path in files:
                file_match = pattern.match(file_path.name)
                if file_match:
                    num_str = file_match.group(1)
                    # Empty string means episode 1, otherwise use the number
                    episode_num = int(num_str) if num_str else 1
                    if episode_num in episode_map:
                        is_valid = False
                        break
                    episode_map[episode_num] = file_path
                else:
                    is_valid = False
                    break

            if is_valid and len(episode_map) == len(files):
                return episode_map

    return {}


def extract_episode_numbers(files: list[Path]) -> dict[int, Path]:
    """
    Intelligently extracts episode numbers from a list of filenames
    by finding a changing numeric part across the list using regex patterns.

    Returns:
        Dictionary mapping episode number to file path.
        Empty dict if pattern detection fails.
    """
    if not files:
        return {}

    # Single file: assume episode 1 (movie case)
    if len(files) == 1:
        return {1: files[0]}

    # Use the first filename as a template to enumerate candidate positions.
    template_name = files[0].name

    # Find every numeric run in the template and, scanning left to right, look
    # for the first one that behaves like an episode counter: its preceding
    # text is identical in every file and its value differs in every file.
    #
    # We anchor only the constant *prefix* up to the candidate number and let
    # the rest of the name vary (`.*`). This is the key to robustness: anything
    # that follows the episode -- resolution tags, per-file CRC32 hashes,
    # variable episode titles (``S02E01.Dawn.and.Confusion``) -- is absorbed by
    # the wildcard instead of having to be literally constant. Static fields
    # such as ``1080`` are rejected because their values are not distinct, and
    # fields *after* the episode reject themselves because their prefix embeds
    # the (varying) episode number.
    numeric_parts = list(re.finditer(r"\d+", template_name))

    for match in numeric_parts:
        prefix = template_name[: match.start()]
        pattern = re.compile(rf"^{re.escape(prefix)}(\d+).*$", re.IGNORECASE)

        # Test this generated pattern against all provided filenames.
        episode_map: dict[int, Path] = {}
        is_pattern_valid = True

        for file_path in files:
            match_obj = pattern.match(file_path.name)
            if match_obj:
                episode_num = int(match_obj.group(1))
                # A valid pattern must not produce duplicate episode numbers:
                # a non-distinct value means this is a static field, not the
                # episode counter.
                if episode_num in episode_map:
                    is_pattern_valid = False
                    break
                episode_map[episode_num] = file_path
            else:
                # If any file doesn't match, this pattern is incorrect.
                is_pattern_valid = False
                break

        # A pattern is considered successful if it matched every single file
        # and each file mapped to a unique episode number.
        if is_pattern_valid and len(episode_map) == len(files):
            return episode_map

    # Try prefixed patterns (OVA, SP, etc.) as fallback. These encode episode 1
    # as a bare textual marker with no digit (e.g. ``OVA``), which no purely
    # numeric rule can recover.
    prefixed_result = _try_prefixed_pattern(files)
    if prefixed_result:
        return prefixed_result

    # No valid pattern found
    return {}
