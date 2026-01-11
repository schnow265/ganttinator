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

    def get_assignee_list(self) -> list[str]:
        """Get list of assignees."""
        if not self.assignees:
            return []
        return [a.strip() for a in self.assignees.split(",") if a.strip()]

    def get_assignee_tuple(self) -> tuple[str, ...]:
        """Get sorted tuple of assignees for grouping."""
        return tuple(sorted(self.get_assignee_list()))

    def to_dict(self) -> dict[str, str]:
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
