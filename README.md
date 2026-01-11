# ganntinator

Please note that this is **not production ready**!

> Ever had to provide a Gantt chart, but you wanted to do it differently? Well, now you can!

Introducing: The Ganntinator!

## Features

- Parses a GitHub Projects TSV export
- Builds a TOML file for [further configuration](#configuration)
- Detects common groups of people working on issues
- Writes a [PlantUML](https://plantuml.com) file.

## Requirements

- Python (preferably using `uv`)
- A GitHub Project with the following fields in a Table (Case-Sensitive):
    - Title
    - Assignees
    - Start date
    - End Date
    - Milestone

## Configuration

You can configure:

- Project Start date
- Milestone Dates
- Group Names
- Colors used
- Labels
- Closed Dates (Weekday, specific date, range)
- Display names (for the times where you can't put your GH account names on a school assingment)
- The Issues themselfes as they are written into the TOML file
- Header and footer for your Diagram
