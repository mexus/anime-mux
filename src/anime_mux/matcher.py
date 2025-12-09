"""Episode number extraction from filenames."""

import re
from pathlib import Path


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

    # No valid pattern found
    return {}
