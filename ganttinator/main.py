import logging
import sys
import uuid
from collections import Counter
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.prompt import Prompt
from rich.table import Table

from ganttinator.config import create_toml_config, load_config_from_toml, save_config_to_toml
from ganttinator.consts import COLOR_PALETTE
from ganttinator.generate import generate_plantuml
from ganttinator.task import Task
from ganttinator.utils import parse_date, read_tsv_file

FORMAT = "%(message)s"
logging.basicConfig(
    level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()]
)

console = Console()
logger = logging.getLogger(__name__)


def detect_assignee_groups(tasks: list[Task], min_occurrences: int = 2) -> list[tuple[str, ...]]:
    """Detect groups of people who are frequently assigned together."""
    assignee_combinations: Counter[tuple[str, ...]] = Counter()

    for task in tasks:
        assignee_tuple = task.get_assignee_tuple()
        if len(assignee_tuple) > 1:  # Only consider groups of 2 or more
            assignee_combinations[assignee_tuple] += 1

    # Filter groups that appear at least min_occurrences times
    frequent_groups = [group for group, count in assignee_combinations.items() if count >= min_occurrences]

    # Sort by frequency (descending) and then by group size (descending)
    frequent_groups.sort(key=lambda g: (assignee_combinations[g], len(g)), reverse=True)

    return frequent_groups


def assign_colors(assignees: set[str], groups: list[tuple[str, ...]]) -> tuple[list[dict], list[dict]]:
    """Assign colors to individual assignees and groups.

    Returns:
        Tuple of (persons list with color info, groups list with color info)
    """
    persons_with_colors: list[dict] = []
    groups_with_colors: list[dict] = []

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


def prompt_project_start_date() -> str | None:
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
        console.print("[red]Invalid date format. Please use 'Jan 8, 2026' or 'YYYY-MM-DD'[/red]")


def collect_milestone_dates(tasks: list[Task]) -> dict[str, str]:
    """Collect unique milestones and prompt for their due dates."""
    milestones: set[str] = {task.milestone for task in tasks if task.milestone}

    if not milestones:
        console.print("[yellow]No milestones found in the TSV file[/yellow]")
        return {}

    console.print("\n[bold cyan]Milestone Due Dates[/bold cyan]")
    console.print("Please enter the due dates for the following milestones (or press Enter to skip):")
    console.print("Format: 'Jan 8, 2026' or 'YYYY-MM-DD'\n")

    milestone_dates: dict[str, str] = {}

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
            console.print("[red]Invalid date format.   Please use 'Jan 8, 2026' or 'YYYY-MM-DD'[/red]")

    return milestone_dates


def prompt_header_footer_legend() -> tuple[str, str, str]:
    """Prompt for header, footer, and legend title text."""
    console.print("\n[bold cyan]Diagram Header, Footer, and Legend[/bold cyan]")

    header = Prompt.ask("Enter header text (or press Enter to skip)", default="")
    footer = Prompt.ask("Enter footer text (or press Enter to skip)", default="")
    legend_title = Prompt.ask("Enter legend title (or press Enter to skip)", default="")

    return header.strip(), footer.strip(), legend_title.strip()


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
    input_tsv: Path | None,
    input_toml: Path | None,
    output_puml: Path,
    output_toml: Path,
    project_start_date: str | None,
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

    for task in tasks:
        table.add_row(
            task.title,
            task.assignees,
            task.start_date,
            task.end_date,
            task.milestone,
        )

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
    all_assignees: set[str] = set()
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
    milestone_dates: dict[str, str] = {}
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
    console.print("\n[cyan]To regenerate from config later, run:[/cyan]")
    console.print(f"  python generate_gantt.py --input-toml {output_toml} --output-puml {output_puml}")


if __name__ == "__main__":
    main()
