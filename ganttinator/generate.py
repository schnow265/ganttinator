from ganttinator.config import load_closed_days_from_config, load_groups_from_config, load_persons_from_config
from ganttinator.main import find_earliest_task_date
from ganttinator.task import Task


def generate_plantuml(
    tasks: list[Task],
    config: dict,
) -> str:
    """Generate PlantUML Gantt diagram code."""
    lines: list[str] = ["@startgantt"]

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
    tasks_by_milestone: dict[str, list[Task]] = {}
    tasks_without_milestone: list[Task] = []

    for task in tasks:
        if task.milestone:
            if task.milestone not in tasks_by_milestone:
                tasks_by_milestone[task.milestone] = []
            tasks_by_milestone[task.milestone].append(task)
        else:
            tasks_without_milestone.append(task)

    # Filter milestones with dates and sort them
    milestones_with_dates = {m: d for m, d in milestone_dates.items() if d}
    sorted_milestones: list[tuple[str, str]] = sorted(milestones_with_dates.items(), key=lambda x: x[1])

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
    for milestone in tasks_by_milestone:
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

def get_task_color(
    task: Task,
    person_colors: dict[str, str],
    group_colors: dict[str, str],
    groups_dict: dict[str, list[str]],
) -> str | None:
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