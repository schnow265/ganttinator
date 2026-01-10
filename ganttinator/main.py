import csv
import sys
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import click
import tomli
import tomli_w
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

console = Console()


# Color palette for assignees/groups
COLOR_PALETTE: List[str] = [
    "LightBlue",
    "LightGreen",
    "LightCoral",
    "LightGoldenRodYellow",
    "LightPink",
    "LightSalmon",
    "LightSeaGreen",
    "LightSkyBlue",
    "LightSteelBlue",
    "PaleGreen",
    "PaleTurquoise",
    "PeachPuff",
    "Plum",
    "PowderBlue",
    "Thistle",
]


class Task:
    """Represents a task from the TSV file."""

    def __init__(
        self,
        title: str,
        url: str,
        assignees: str,
        start_date: str,
        end_date: str,
        milestone: str,
    ) -> None:
        self.title: str = title
        self.url: str = url
        self.assignees: str = assignees
        self.start_date: str = start_date
        self.end_date: str = end_date
        self.milestone: str = milestone

    def __repr__(self) -> str:
        return f"Task({self.title}, {self.start_date} - {self.end_date})"

    def get_assignee_list(self) -> List[str]:
        """Get list of assignees."""
        if not self.assignees:
            return []
        return [a.strip() for a in self.assignees.split(",") if a.strip()]

    def get_assignee_tuple(self) -> Tuple[str, ...]:
        """Get sorted tuple of assignees for grouping."""
        return tuple(sorted(self.get_assignee_list()))

    def to_dict(self) -> dict:
        """Convert task to dictionary for TOML storage."""
        return {
            "title": self.title,
            "url": self.url,
            "assignees": self.assignees,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "milestone": self.milestone,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Create task from dictionary."""
        return cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            assignees=data.get("assignees", ""),
            start_date=data.get("start_date", ""),
            end_date=data.get("end_date", ""),
            milestone=data.get("milestone", ""),
        )


def parse_date(date_str: str) -> Optional[str]:
    """Parse date from 'Jan 8, 2026' or 'YYYY-MM-DD' format to 'YYYY-MM-DD'."""
    if not date_str:
        return None

    date_str = date_str.strip()

    # Try YYYY-MM-DD format first
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass

    # Try 'Jan 8, 2026' format
    try:
        dt = datetime.strptime(date_str, "%b %d, %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass

    # Try 'January 8, 2026' format
    try:
        dt = datetime.strptime(date_str, "%B %d, %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass

    return None


def validate_date(date_str: str) -> bool:
    """Validate date format."""
    if not date_str:
        return True  # Empty dates are allowed
    return parse_date(date_str) is not None


def read_tsv_file(filepath: Path) -> List[Task]:
    """Read TSV file and return list of tasks."""
    tasks: List[Task] = []

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")

        if not reader.fieldnames:
            console.print("[red]Error: TSV file is empty[/red]")
            sys.exit(1)

        required_columns = {
            "Title",
            "URL",
            "Assignees",
            "Start date",
            "End Date",
            "Milestone",
        }
        missing_columns = required_columns - set(reader.fieldnames)

        if missing_columns:
            console.print(f"[red]Error: Missing required columns: {missing_columns}[/red]")
            sys.exit(1)

        for row_num, row in enumerate(reader, start=2):
            title = row["Title"].strip()
            url = row["URL"].strip()
            assignees = row["Assignees"].strip()
            start_date = row["Start date"].strip()
            end_date = row["End Date"].strip()
            milestone = row["Milestone"].strip()

            if not title:
                console.print(f"[yellow]Warning: Row {row_num} has empty title[/yellow]")
                continue

            # Parse and validate start date
            if start_date:
                parsed_start = parse_date(start_date)
                if parsed_start is None:
                    console.print(f"[yellow]Warning: Row {row_num} has invalid start date:   {start_date}[/yellow]")
                    start_date = ""
                else:
                    start_date = parsed_start

            # Parse and validate end date
            if end_date:
                parsed_end = parse_date(end_date)
                if parsed_end is None:
                    console.print(f"[yellow]Warning: Row {row_num} has invalid end date:   {end_date}[/yellow]")
                    end_date = ""
                else:
                    end_date = parsed_end

            tasks.append(Task(title, url, assignees, start_date, end_date, milestone))

    return tasks


def detect_assignee_groups(tasks: List[Task], min_occurrences: int = 2) -> List[Tuple[str, ...]]:
    """Detect groups of people who are frequently assigned together."""
    assignee_combinations: Counter[Tuple[str, ...]] = Counter()

    for task in tasks:
        assignee_tuple = task.get_assignee_tuple()
        if len(assignee_tuple) > 1:  # Only consider groups of 2 or more
            assignee_combinations[assignee_tuple] += 1

    # Filter groups that appear at least min_occurrences times
    frequent_groups = [group for group, count in assignee_combinations.items() if count >= min_occurrences]

    # Sort by frequency (descending) and then by group size (descending)
    frequent_groups.sort(key=lambda g: (assignee_combinations[g], len(g)), reverse=True)

    return frequent_groups


def assign_colors(assignees: Set[str], groups: List[Tuple[str, ...]]) -> Tuple[List[dict], List[dict]]:
    """Assign colors to individual assignees and groups.

    Returns:
        Tuple of (persons list with color info, groups list with color info)
    """
    persons_with_colors: List[dict] = []
    groups_with_colors: List[dict] = []

    color_index = 0

    # Assign colors to all individual assignees
    for assignee in sorted(assignees):
        color = ""
        if color_index < len(COLOR_PALETTE):
            color = COLOR_PALETTE[color_index]
            color_index += 1
        else:
            # Fallback to default color if we run out
            color = "LightGray"

        persons_with_colors.append({
            "name": assignee,
            "display_name": "",  # Empty by default, user can edit in TOML
            "color": color,
        })

    # Assign colors to groups with UUIDs
    for group in groups:
        color = ""
        if color_index < len(COLOR_PALETTE):
            color = COLOR_PALETTE[color_index]
            color_index += 1

        group_name = " & ".join(group)
        groups_with_colors.append({
            "uuid": str(uuid.uuid4()),
            "name": group_name,
            "members": list(group),
            "color": color,
        })

    return persons_with_colors, groups_with_colors


def prompt_project_start_date() -> Optional[str]:
    """Prompt user for the project start date."""
    console.print("\n[bold cyan]Project Start Date[/bold cyan]")
    console.print("Please enter the project start date (or press Enter to skip):")
    console.print("Format: 'Jan 8, 2026' or 'YYYY-MM-DD'\n")

    while True:
        date_str = Prompt.ask("Project start date", default="")
        date_str = date_str.strip()

        if not date_str:
            console.print("[yellow]Skipping project start date[/yellow]")
            return None

        parsed_date = parse_date(date_str)
        if parsed_date:
            return parsed_date
        else:
            console.print("[red]Invalid date format. Please use 'Jan 8, 2026' or 'YYYY-MM-DD'[/red]")


def collect_milestone_dates(tasks: List[Task]) -> Dict[str, str]:
    """Collect unique milestones and prompt for their due dates."""
    milestones: set[str] = {task.milestone for task in tasks if task.milestone}

    if not milestones:
        console.print("[yellow]No milestones found in the TSV file[/yellow]")
        return {}

    console.print("\n[bold cyan]Milestone Due Dates[/bold cyan]")
    console.print("Please enter the due dates for the following milestones (or press Enter to skip):")
    console.print("Format: 'Jan 8, 2026' or 'YYYY-MM-DD'\n")

    milestone_dates: Dict[str, str] = {}

    for milestone in sorted(milestones):
        while True:
            date_str = Prompt.ask(f"Due date for milestone '[green]{milestone}[/green]'", default="")
            date_str = date_str.strip()

            if not date_str:
                console.print("[yellow]Skipping milestone date (will be saved with empty date)[/yellow]")
                milestone_dates[milestone] = ""
                break

            parsed_date = parse_date(date_str)
            if parsed_date:
                milestone_dates[milestone] = parsed_date
                break
            else:
                console.print("[red]Invalid date format.   Please use 'Jan 8, 2026' or 'YYYY-MM-DD'[/red]")

    return milestone_dates


def prompt_header_footer_legend() -> Tuple[str, str, str]:
    """Prompt for header, footer, and legend title text."""
    console.print("\n[bold cyan]Diagram Header, Footer, and Legend[/bold cyan]")

    header = Prompt.ask("Enter header text (or press Enter to skip)", default="")
    footer = Prompt.ask("Enter footer text (or press Enter to skip)", default="")
    legend_title = Prompt.ask("Enter legend title (or press Enter to skip)", default="")

    return header.strip(), footer.strip(), legend_title.strip()


def create_toml_config(
    tasks: List[Task],
    project_start_date: Optional[str],
    milestone_dates: Dict[str, str],
    persons_with_colors: List[dict],
    groups_with_colors: List[dict],
    header: str,
    footer: str,
    legend_title: str,
) -> dict:
    """Create TOML configuration dictionary."""
    config = {
        "project": {
            "start_date": project_start_date if project_start_date else "",
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


def load_persons_from_config(config: dict) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Load persons from config and return color and display name mappings.

    Returns:
        Tuple of (person_colors mapping name to color,
                  person_display_names mapping name to display name)
    """
    person_colors: Dict[str, str] = {}
    person_display_names: Dict[str, str] = {}

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


def load_groups_from_config(config: dict) -> Tuple[Dict[str, List[str]], Dict[str, str], Dict[str, str]]:
    """Load groups from config and return as dictionaries.

    Returns:
        Tuple of (groups_dict mapping name to members,
                  group_colors mapping name to color,
                  uuid_to_name mapping UUID to current group name)
    """
    groups_dict: Dict[str, List[str]] = {}
    group_colors: Dict[str, str] = {}
    uuid_to_name: Dict[str, str] = {}

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


def load_closed_days_from_config(config: dict) -> Tuple[List[str], List[str], List[Tuple[str, str]]]:
    """Load closed days from config.

    Returns:
        Tuple of (list of closed weekdays, list of individual closed dates, list of closed date range tuples)
    """
    closed_days_config = config.get("closed_days", {})

    closed_weekdays: List[str] = closed_days_config.get("weekdays", ["saturday", "sunday"])
    closed_dates: List[str] = closed_days_config.get("dates", [])
    closed_date_ranges_raw = closed_days_config.get("date_ranges", [])

    # Parse date ranges
    closed_date_ranges: List[Tuple[str, str]] = []
    for date_range in closed_date_ranges_raw:
        if isinstance(date_range, list) and len(date_range) == 2:
            closed_date_ranges.append((date_range[0], date_range[1]))

    return closed_weekdays, closed_dates, closed_date_ranges


def load_config_from_toml(filepath: Path) -> dict:
    """Load configuration from TOML file."""
    with open(filepath, "rb") as f:
        return tomli.load(f)


def save_config_to_toml(config: dict, filepath: Path) -> None:
    """Save configuration to TOML file."""
    with open(filepath, "wb") as f:
        tomli_w.dump(config, f)
    console.print(f"[green]Configuration saved to:[/green] {filepath}")


def get_task_color(
    task: Task,
    person_colors: Dict[str, str],
    group_colors: Dict[str, str],
    groups_dict: Dict[str, List[str]],
) -> Optional[str]:
    """Get the color for a task based on its assignees."""
    assignees = task.get_assignee_list()

    if not assignees:
        return None

    # Check if assignees match a group
    assignee_set = set(assignees)
    for group_name, group_members in groups_dict.items():
        if assignee_set == set(group_members):
            return group_colors.get(group_name)

    # Use color of first assignee
    if assignees[0] in person_colors:
        return person_colors[assignees[0]]

    return None


def escape_plantuml_text(text: str) -> str:
    """Escape special characters for PlantUML."""
    text = text.replace("[", "(").replace("]", ")")
    return text


def find_earliest_task_date(tasks: List[Task]) -> Optional[str]:
    """Find the earliest date among all tasks."""
    dates = []
    for task in tasks:
        if task.start_date:
            dates.append(task.start_date)
        if task.end_date:
            dates.append(task.end_date)

    return min(dates) if dates else None


def generate_plantuml(
    tasks: List[Task],
    config: dict,
) -> str:
    """Generate PlantUML Gantt diagram code."""
    lines: List[str] = ["@startgantt"]

    project_start_date = config["project"]["start_date"]
    milestone_dates = config["milestones"]
    header = config["project"].get("header", "")
    footer = config["project"].get("footer", "")
    person_colors, person_display_names = load_persons_from_config(config)
    groups_dict, group_colors, uuid_to_name = load_groups_from_config(config)
    legend_config = config.get("legend", {})
    closed_weekdays, closed_dates, closed_date_ranges = load_closed_days_from_config(config)

    # Add header
    if header:
        lines.append(f"title {escape_plantuml_text(header)}")
        lines.append("")

    # Add project start date if provided
    if project_start_date:
        lines.append(f"Project starts {project_start_date}")
        lines.append("")
    else:
        # Try to find earliest date from tasks or milestones
        earliest_date = find_earliest_task_date(tasks)
        if not earliest_date:
            # Check milestones for earliest date
            milestone_dates_only = [d for d in milestone_dates.values() if d]
            if milestone_dates_only:
                earliest_date = min(milestone_dates_only)

        if earliest_date:
            lines.append(f"Project starts {earliest_date}")
            lines.append("")

    # Add project settings
    lines.append("printscale daily")

    # Add closed weekdays
    for weekday in closed_weekdays:
        if weekday:  # Skip empty strings
            # Ensure lowercase for PlantUML
            weekday_lower = weekday.lower().strip()
            if weekday_lower in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
                lines.append(f"{weekday_lower} are closed")

    lines.append("")

    # Add closed days
    for closed_date in closed_dates:
        if closed_date:  # Skip empty strings
            lines.append(f"{closed_date} is closed")

    # Add closed date ranges
    for start_date, end_date in closed_date_ranges:
        if start_date and end_date:  # Skip if either is empty
            lines.append(f"{start_date} to {end_date} is closed")

    if closed_dates or closed_date_ranges:
        lines.append("")

    # Add legend if enabled
    if legend_config.get("enabled", False):
        lines.append("legend")

        # Add legend title if provided
        legend_title = legend_config.get("title", "")
        if legend_title:
            lines.append(f"<b>{escape_plantuml_text(legend_title)}</b>")

        for item_ref, item_color in legend_config.get("items", []):
            # Parse the reference to determine if it's a group or person
            if item_ref.startswith("group:"):
                group_uuid = item_ref[6:]  # Remove "group:" prefix
                group_name = uuid_to_name.get(group_uuid, f"Unknown Group ({group_uuid[:8]})")
                lines.append(f"|<back:{item_color}>    </back>| {escape_plantuml_text(group_name)} |")
            elif item_ref.startswith("person:"):
                person_name = item_ref[7:]  # Remove "person:" prefix
                # Use display name if available, otherwise use name
                display_name = person_display_names.get(person_name, person_name)
                lines.append(f"|<back:{item_color}>    </back>| {escape_plantuml_text(display_name)} |")
            else:
                # Fallback for legacy format
                lines.append(f"|<back:{item_color}>    </back>| {escape_plantuml_text(item_ref)} |")
        lines.append("endlegend")
        lines.append("")

    # Group tasks by milestone
    tasks_by_milestone: Dict[str, List[Task]] = {}
    tasks_without_milestone: List[Task] = []

    for task in tasks:
        if task.milestone:
            if task.milestone not in tasks_by_milestone:
                tasks_by_milestone[task.milestone] = []
            tasks_by_milestone[task.milestone].append(task)
        else:
            tasks_without_milestone.append(task)

    # Filter milestones with dates and sort them
    milestones_with_dates = {m: d for m, d in milestone_dates.items() if d}
    sorted_milestones: List[Tuple[str, str]] = sorted(milestones_with_dates.items(), key=lambda x: x[1])

    # Add milestones sorted by date (only those with dates)
    for milestone, date in sorted_milestones:
        safe_milestone = escape_plantuml_text(milestone)
        lines.append(f"[{safe_milestone}] happens at {date}")

    if sorted_milestones:
        lines.append("")

    # Add vertical lines for milestones
    for milestone, date in sorted_milestones:
        lines.append(f"{date} is colored in LightGray")

    if sorted_milestones:
        lines.append("")

    # Add tasks grouped by milestone (sorted by milestone due date, then undated milestones)
    # First, process milestones with dates in order
    for milestone, _ in sorted_milestones:
        if milestone not in tasks_by_milestone:
            continue

        milestone_tasks = tasks_by_milestone[milestone]
        lines.append(f"-- {escape_plantuml_text(milestone)} --")

        for task in milestone_tasks:
            safe_title = escape_plantuml_text(task.title)

            if task.start_date:
                lines.append(f"[{safe_title}] starts {task.start_date}")

            if task.end_date:
                lines.append(f"[{safe_title}] ends {task.end_date}")
            elif task.start_date:
                lines.append(f"[{safe_title}] lasts 1 days")

            if not task.start_date and not task.end_date:
                # Only use milestone date if it exists
                if milestone in milestones_with_dates:
                    lines.append(f"[{safe_title}] happens at {milestones_with_dates[milestone]}")

            # Apply color based on assignees
            color = get_task_color(task, person_colors, group_colors, groups_dict)
            if color:
                lines.append(f"[{safe_title}] is colored in {color}")

        lines.append("")

    # Add milestones without dates but with tasks
    for milestone in tasks_by_milestone.keys():
        if milestone not in milestones_with_dates:
            milestone_tasks = tasks_by_milestone[milestone]
            lines.append(f"-- {escape_plantuml_text(milestone)} --")

            for task in milestone_tasks:
                safe_title = escape_plantuml_text(task.title)

                if task.start_date:
                    lines.append(f"[{safe_title}] starts {task.start_date}")

                if task.end_date:
                    lines.append(f"[{safe_title}] ends {task.end_date}")
                elif task.start_date:
                    lines.append(f"[{safe_title}] lasts 1 days")

                # Apply color based on assignees
                color = get_task_color(task, person_colors, group_colors, groups_dict)
                if color:
                    lines.append(f"[{safe_title}] is colored in {color}")

            lines.append("")

    # Add tasks without milestone
    if tasks_without_milestone:
        lines.append("-- Other Tasks --")
        for task in tasks_without_milestone:
            safe_title = escape_plantuml_text(task.title)

            if task.start_date:
                lines.append(f"[{safe_title}] starts {task.start_date}")

            if task.end_date:
                lines.append(f"[{safe_title}] ends {task.end_date}")
            elif task.start_date:
                lines.append(f"[{safe_title}] lasts 1 days")

            # Apply color based on assignees
            color = get_task_color(task, person_colors, group_colors, groups_dict)
            if color:
                lines.append(f"[{safe_title}] is colored in {color}")

        lines.append("")

    # Add footer
    if footer:
        lines.append(f"footer {escape_plantuml_text(footer)}")
        lines.append("")

    lines.append("@endgantt")

    return "\n".join(lines)


@click.command()
@click.option(
    "--input-tsv",
    type=click.Path(exists=True, path_type=Path),
    help="Path to the TSV file containing task data",
)
@click.option(
    "--input-toml",
    type=click.Path(exists=True, path_type=Path),
    help="Path to the TOML configuration file",
)
@click.option(
    "--output-puml",
    type=click.Path(path_type=Path),
    default="gantt.puml",
    help="Path where the PlantUML file will be saved",
)
@click.option(
    "--output-toml",
    type=click.Path(path_type=Path),
    default="gantt_config.toml",
    help="Path where the TOML configuration will be saved",
)
@click.option(
    "--project-start-date",
    type=str,
    help="Project start date (format: 'Jan 8, 2026' or 'YYYY-MM-DD')",
)
@click.option(
    "--no-milestone-prompt",
    is_flag=True,
    help="Skip prompting for milestone due dates",
)
@click.option(
    "--min-group-occurrences",
    type=int,
    default=2,
    help="Minimum occurrences to consider an assignee combination as a group",
)
def main(
    input_tsv: Optional[Path],
    input_toml: Optional[Path],
    output_puml: Path,
    output_toml: Path,
    project_start_date: Optional[str],
    no_milestone_prompt: bool,
    min_group_occurrences: int,
) -> None:
    """Generate PlantUML Gantt diagram from TSV file or TOML configuration.

    Mode 1: Generate from TSV (creates both TOML config and PlantUML diagram)
        --input-tsv FILE

    Mode 2: Regenerate from TOML (updates PlantUML diagram from existing config)
        --input-toml FILE
    """
    if not input_tsv and not input_toml:
        console.print("[red]Error: Either --input-tsv or --input-toml must be specified[/red]")
        sys.exit(1)

    if input_tsv and input_toml:
        console.print("[red]Error: Cannot specify both --input-tsv and --input-toml[/red]")
        sys.exit(1)

    # Mode 2:   Regenerate from TOML
    if input_toml:
        console.print(f"[bold]Loading configuration from:[/bold] {input_toml}")
        config = load_config_from_toml(input_toml)

        # Parse tasks from TOML
        tasks = [Task.from_dict(task_data) for task_data in config.get("tasks", [])]

        console.print(f"[green]Loaded {len(tasks)} tasks from configuration[/green]")
        console.print("\n[bold]Generating PlantUML diagram from configuration..  .[/bold]")

        plantuml_code = generate_plantuml(tasks, config)
        output_puml.write_text(plantuml_code, encoding="utf-8")

        console.print(f"[green]Successfully wrote PlantUML diagram to:[/green] {output_puml}")
        console.print(f"\n[cyan]To generate the diagram image, run:[/cyan] plantuml {output_puml}")
        return

    # Mode 1: Generate from TSV
    console.print(f"[bold]Reading tasks from:[/bold] {input_tsv}")
    tasks = read_tsv_file(input_tsv)

    if not tasks:
        console.print("[red]No valid tasks found in the input file[/red]")
        sys.exit(1)

    console.print(f"[green]Successfully read {len(tasks)} tasks[/green]\n")

    # Display tasks in a table
    table = Table(title="Tasks Overview")
    table.add_column("Title", style="cyan")
    table.add_column("Assignees", style="magenta")
    table.add_column("Start Date", style="green")
    table.add_column("End Date", style="green")
    table.add_column("Milestone", style="yellow")

    for task in tasks[:10]:
        table.add_row(
            task.title,
            task.assignees,
            task.start_date,
            task.end_date,
            task.milestone,
        )

    if len(tasks) > 10:
        table.add_row("..  .", ".. .", "...", "...", "...")

    console.print(table)
    console.print()

    # Detect assignee groups
    console.print("[bold]Detecting assignee groups.. .[/bold]")
    groups = detect_assignee_groups(tasks, min_group_occurrences)

    if groups:
        console.print(f"[green]Found {len(groups)} frequent assignee groups:[/green]")
        for group in groups:
            console.print(f"  - {' & '.join(group)}")
    else:
        console.print("[yellow]No frequent assignee groups found[/yellow]")
    console.print()

    # Collect all unique assignees
    all_assignees: Set[str] = set()
    for task in tasks:
        all_assignees.update(task.get_assignee_list())

    # Assign colors
    persons_with_colors, groups_with_colors = assign_colors(all_assignees, groups)

    # Get project start date
    if project_start_date:
        parsed_start = parse_date(project_start_date)
        if parsed_start is None:
            console.print("[red]Invalid project start date format. Please use 'Jan 8, 2026' or 'YYYY-MM-DD'[/red]")
            sys.exit(1)
        project_start_date = parsed_start
    else:
        project_start_date = prompt_project_start_date()

    # Collect milestone dates
    milestone_dates: Dict[str, str] = {}
    if not no_milestone_prompt:
        milestone_dates = collect_milestone_dates(tasks)

    # Prompt for header, footer, and legend title
    header, footer, legend_title = prompt_header_footer_legend()

    # Create TOML configuration
    config = create_toml_config(
        tasks,
        project_start_date,
        milestone_dates,
        persons_with_colors,
        groups_with_colors,
        header,
        footer,
        legend_title,
    )

    # Save TOML configuration
    save_config_to_toml(config, output_toml)

    # Generate PlantUML
    console.print("\n[bold]Generating PlantUML diagram...[/bold]")
    plantuml_code = generate_plantuml(tasks, config)

    # Write to file
    output_puml.write_text(plantuml_code, encoding="utf-8")

    console.print(f"[green]Successfully wrote PlantUML diagram to:[/green] {output_puml}")
    console.print(f"\n[cyan]To generate the diagram image, run:[/cyan] plantuml {output_puml}")
    console.print(f"\n[cyan]To regenerate from config later, run:[/cyan]")
    console.print(f"  python generate_gantt.  py --input-toml {output_toml} --output-puml {output_puml}")


if __name__ == "__main__":
    main()
