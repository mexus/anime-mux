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
                f"^{re.escape(before)}"
                f"(?:{re.escape(prefix)})(\\d*)"
                f"{re.escape(after)}$"
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

    # Use the first filename as a template to generate potential patterns.
    template_name = files[0].name

    # Find all numeric sequences in the template filename.
    # We iterate through them in reverse order, as episode numbers are often
    # found later in filenames and are less likely to be static parts like '1080p'.
    numeric_parts = list(re.finditer(r"\d+", template_name))

    for match in reversed(numeric_parts):
        # Create a regex pattern by replacing this number with a capture group
        # for any digit sequence.
        prefix = template_name[: match.start()]
        suffix = template_name[match.end() :]

        # The pattern: escape the prefix and suffix to treat them as literal strings,
        # and place a digit capture group (\d+) in the middle.
        pattern_str = f"^{re.escape(prefix)}(\\d+){re.escape(suffix)}$"
        pattern = re.compile(pattern_str, re.IGNORECASE)

        # Test this generated pattern against all provided filenames.
        episode_map: dict[int, Path] = {}
        is_pattern_valid = True

        for file_path in files:
            match_obj = pattern.match(file_path.name)
            if match_obj:
                episode_num = int(match_obj.group(1))
                # A valid pattern must not produce duplicate episode numbers
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

    # Try prefixed patterns (OVA, SP, etc.) as fallback
    prefixed_result = _try_prefixed_pattern(files)
    if prefixed_result:
        return prefixed_result

    # No valid pattern found
    return {}
