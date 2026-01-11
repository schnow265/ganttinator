import logging
from pathlib import Path

import tomli
import tomli_w
from rich.console import Console

from ganttinator.task import Task

console = Console()
logger = logging.getLogger(__name__)


def create_toml_config(
    tasks: list[Task],
    project_start_date: str | None,
    milestone_dates: dict[str, str],
    persons_with_colors: list[dict],
    groups_with_colors: list[dict],
    header: str,
    footer: str,
    legend_title: str,
) -> dict:
    """Create TOML configuration dictionary."""
    config = {
        "project": {
            "start_date": project_start_date or "",
            "header": header,
            "footer": footer,
        },
        "closed_days": {
            "weekdays": ["saturday", "sunday"],
            "dates": [],
            "date_ranges": [],
        },
        "milestones": milestone_dates,
        "colors": {
            "persons": persons_with_colors,
        },
        "groups": groups_with_colors,
        "legend": {
            "enabled": True,
            "title": legend_title,
            "items": [],
        },
        "tasks": [],
    }

    # Build legend items (groups first using UUID, then individuals)
    legend_items = []
    for group_data in groups_with_colors:
        # Use UUID as reference for groups
        legend_items.append([f"group:{group_data['uuid']}", group_data["color"]])
    for person_data in persons_with_colors:
        legend_items.append([f"person:{person_data['name']}", person_data["color"]])

    config["legend"]["items"] = legend_items

    # Store tasks as structured objects
    config["tasks"] = [task.to_dict() for task in tasks]

    return config


def load_persons_from_config(config: dict) -> tuple[dict[str, str], dict[str, str]]:
    """Load persons from config and return color and display name mappings.

    Returns:
        Tuple of (person_colors mapping name to color,
                  person_display_names mapping name to display name)
    """
    person_colors: dict[str, str] = {}
    person_display_names: dict[str, str] = {}

    persons_list = config.get("colors", {}).get("persons", [])

    # Handle both old format (dict) and new format (list of dicts)
    if isinstance(persons_list, dict):
        # Legacy format:   {"alice": "LightBlue"}
        person_colors = persons_list
    else:
        # New format:   [{"name": "alice", "display_name": "Alice", "color": "LightBlue"}]
        for person_data in persons_list:
            if isinstance(person_data, dict):
                name = person_data.get("name", "")
                color = person_data.get("color", "")
                display_name = person_data.get("display_name", "")
                if name:
                    if color:
                        person_colors[name] = color
                    if display_name:
                        person_display_names[name] = display_name

    return person_colors, person_display_names


def load_groups_from_config(config: dict) -> tuple[dict[str, list[str]], dict[str, str], dict[str, str]]:
    """Load groups from config and return as dictionaries.

    Returns:
        Tuple of (groups_dict mapping name to members,
                  group_colors mapping name to color,
                  uuid_to_name mapping UUID to current group name)
    """
    groups_dict: dict[str, list[str]] = {}
    group_colors: dict[str, str] = {}
    uuid_to_name: dict[str, str] = {}

    groups_list = config.get("groups", [])
    for group_data in groups_list:
        if isinstance(group_data, dict):
            group_uuid = group_data.get("uuid", "")
            name = group_data.get("name", "")
            members = group_data.get("members", [])
            color = group_data.get("color", "")
            if name and members:
                groups_dict[name] = members
                if color:
                    group_colors[name] = color
                if group_uuid:
                    uuid_to_name[group_uuid] = name

    return groups_dict, group_colors, uuid_to_name


def load_closed_days_from_config(config: dict) -> tuple[list[str], list[str], list[tuple[str, str]]]:
    """Load closed days from config.

    Returns:
        Tuple of (list of closed weekdays, list of individual closed dates, list of closed date range tuples)
    """
    closed_days_config = config.get("closed_days", {})

    closed_weekdays: list[str] = closed_days_config.get("weekdays", ["saturday", "sunday"])
    closed_dates: list[str] = closed_days_config.get("dates", [])
    closed_date_ranges_raw = closed_days_config.get("date_ranges", [])

    # Parse date ranges
    closed_date_ranges: list[tuple[str, str]] = []
    for date_range in closed_date_ranges_raw:
        if isinstance(date_range, list) and len(date_range) == 2:
            closed_date_ranges.append((date_range[0], date_range[1]))

    return closed_weekdays, closed_dates, closed_date_ranges


def load_config_from_toml(filepath: Path) -> dict:
    """Load configuration from TOML file."""
    with Path(filepath).open("rb") as f:
        return tomli.load(f)


def save_config_to_toml(config: dict, filepath: Path) -> None:
    """Save configuration to TOML file."""
    with Path(filepath).open("wb") as f:
        tomli_w.dump(config, f)
    console.print(f"[green]Configuration saved to:[/green] {filepath}")
