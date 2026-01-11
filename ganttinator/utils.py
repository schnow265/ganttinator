import csv
import logging
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console

from ganttinator.task import Task

console = Console()
logger = logging.getLogger(__name__)


def parse_date(date_str: str) -> str | None:
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


def read_tsv_file(filepath: Path) -> list[Task]:
    """Read TSV file and return list of tasks."""
    tasks: list[Task] = []

    logger.debug(f"Reading TSV file '{filepath.absolute()}'")
    with Path(filepath).open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")

        if not reader.fieldnames:
            logger.error("TSV file is empty")
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
            logger.error(f"Missing required columns: {missing_columns}")
            sys.exit(1)

        for row_num, row in enumerate(reader, start=2):
            title = row["Title"].strip()
            url = row["URL"].strip()
            assignees = row["Assignees"].strip()
            start_date = row["Start date"].strip()
            end_date = row["End Date"].strip()
            milestone = row["Milestone"].strip()

            if not title:
                logger.warning(f"Row {row_num} has empty title")
                continue
            
            if not assignees:
                logger.warning(f"Row {row_num} ('{title}') has no assignee.")

            if not start_date:
                logger.warning(f"Row {row_num} ('{title}') has no start date.")

            if not start_date:
                logger.warning(f"Row {row_num} ('{title}') has no end date.")

            # Parse and validate start date
            if start_date:
                parsed_start = parse_date(start_date)
                if parsed_start is None:
                    logger.warning(f"Row {row_num} has invalid start date: '{start_date}'")
                    start_date = ""
                else:
                    start_date = parsed_start

            # Parse and validate end date
            if end_date:
                parsed_end = parse_date(end_date)
                if parsed_end is None:
                    logger.warning(f"Row {row_num} has invalid end date: '{end_date}'")
                    end_date = ""
                else:
                    end_date = parsed_end

            tasks.append(Task(title, url, assignees, start_date, end_date, milestone))

    return tasks


def find_earliest_task_date(tasks: list[Task]) -> str | None:
    """Find the earliest date among all tasks."""
    dates = []
    for task in tasks:
        if task.start_date:
            dates.append(task.start_date)
        if task.end_date:
            dates.append(task.end_date)

    return min(dates) if dates else None
