"""Terminal output helpers: tables, JSON, status messages.

Data goes to stdout (so it can be piped); messages go to stderr.
Color is disabled for `--no-color`, `NO_COLOR`, or when stdout is not a TTY.
"""

import json
import os
import shutil
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# (key in row dict, column header)
Column = Tuple[str, str]


@dataclass
class GlobalOptions:
    json_mode: bool = False
    no_color: bool = False
    quiet: bool = False
    yes: bool = False

    @property
    def color(self) -> bool:
        if self.no_color or os.environ.get("NO_COLOR"):
            return False
        return sys.stdout.isatty()


_ANSI = {"green": "32", "red": "31", "yellow": "33", "bold": "1", "dim": "2"}


def style(text: str, name: str, color: bool) -> str:
    if not color:
        return text
    return f"\x1b[{_ANSI[name]}m{text}\x1b[0m"


def _cell(value: Any) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def render_table(
    rows: Sequence[Dict[str, Any]],
    columns: Sequence[Column],
    color: bool = False,
    max_width: Optional[int] = None,
) -> str:
    """Render rows as an aligned text table with a header row.

    If `max_width` is given and the table is wider, the last column is
    shortened with an ellipsis (it is the free-text column in our tables).
    """
    headers = [h for _, h in columns]
    body: List[List[str]] = [[_cell(r.get(k)) for k, _ in columns] for r in rows]
    widths = [max([len(h)] + [len(line[i]) for line in body]) for i, h in enumerate(headers)]

    if max_width and len(widths) > 1:
        gaps = 2 * (len(widths) - 1)
        room = max_width - (sum(widths[:-1]) + gaps)
        floor = max(len(headers[-1]), 10)
        if sum(widths) + gaps > max_width and room >= floor:
            widths[-1] = room
            for line in body:
                if len(line[-1]) > room:
                    line[-1] = line[-1][: room - 1] + "…"

    def fmt(cells: Iterable[str]) -> str:
        return "  ".join(c.ljust(w) for c, w in zip(cells, widths)).rstrip()

    head = fmt(headers)
    lines = [style(head, "bold", color)] + [fmt(line) for line in body]
    return "\n".join(lines)


def emit_data(
    rows: Sequence[Dict[str, Any]],
    columns: Sequence[Column],
    opts: GlobalOptions,
    footer: Optional[str] = None,
    quiet_key: Optional[str] = None,
) -> None:
    """Print a list of records as JSON, ids-only (quiet), or a table."""
    if opts.json_mode:
        print(json.dumps(list(rows), indent=2, ensure_ascii=False, default=str))
        return
    if opts.quiet and quiet_key:
        for row in rows:
            print(row.get(quiet_key, ""))
        return
    width = shutil.get_terminal_size((100, 24)).columns if sys.stdout.isatty() else None
    print(render_table(rows, columns, opts.color, max_width=width))
    if footer and not opts.quiet:
        print(style(footer, "dim", opts.color), file=sys.stderr)


def render_details(pairs: Sequence[Tuple[str, Any]], color: bool = False) -> str:
    """Render label/value pairs as an aligned block (skipping nothing; blanks show '-')."""
    width = max(len(label) for label, _ in pairs)
    return "\n".join(f"{style(label.ljust(width), 'bold', color)}  {_cell(value)}" for label, value in pairs)


def success(message: str, opts: GlobalOptions) -> None:
    if not opts.quiet:
        print(style("✓ ", "green", opts.color) + message, file=sys.stderr)


def error(message: str, opts: Optional[GlobalOptions] = None) -> None:
    color = opts.color if opts else False
    print(style("✗ ", "red", color) + message, file=sys.stderr)
