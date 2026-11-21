# Work Tracker Design System

Code lives in `src/ui/design/`. The goal: views describe *what* a thing is
(a card, a primary button, a title) and never *how it looks* (hex codes, pixel
sizes, per-widget stylesheets).

## Structure

| File | Purpose |
|------|---------|
| `tokens.py` | Primitive palette, semantic `Theme`, spacing, radii, type scale |
| `qss.py` | Generates the one application stylesheet from tokens |
| `widgets.py` | `Card`, `StatCard`, `PageHeader`, `label()`, `button()`, `set_prop()` |
| `__init__.py` | `apply_theme(app)` and public exports |

`src/ui/theme.py` is a compatibility shim for older views. New code should not use it.

## How it works

1. **Tokens in two layers.** Primitives (`blue-500`) are raw values. A `Theme`
   maps *roles* (`accent`, `surface`, `text_muted`) to primitives. Widgets only
   ever see roles.
2. **QSS is generated.** QSS has no variables, so `build_stylesheet(theme)`
   templates one global stylesheet from the tokens. `gui_main.py` installs it
   once with `apply_theme(app)`.
3. **Variants are Qt dynamic properties.** `QPushButton[variant="danger"]`,
   `QLabel[role="title"]`, `QFrame[card="true"]`. No object names or per-widget
   stylesheets needed.
4. **Changing a variant at runtime** needs a re-polish. Use `set_prop(widget, "variant", "danger")`.

## Using it

```python
from src.ui.design import SPACE, Card, PageHeader, StatCard, button, label, set_prop

header = PageHeader("Projects", "Everything you are tracking")
header.add_action(button("Refresh", "secondary"))

card = Card()
card.body.addWidget(label("Total hours", "overline"))
card.body.addWidget(label("42", "metric", tone="accent"))

layout.setSpacing(SPACE["lg"])          # never a bare number
```

### Roles (`label(text, role)`)
`display` 26 · `title` 22 · `heading` 16 · `body` 13 · `caption` 12 · `overline` 11 caps · `metric` 28
Tones: `accent`, `success`, `danger`.

### Button variants
`primary` · `secondary` (outlined) · `success` · `danger`. Disabled state is automatic.

### Spacing / radius
Spacing: `xxs 2, xs 4, sm 8, md 12, lg 16, xl 24, xxl 32`. Radius: `sm 6, md 8, lg 12`.

## Rules

- No hex colors or `setStyleSheet(...)` in views. If you need a new look, add a
  token or a variant to `qss.py`.
- Cards are `Card()` (or `QFrame[card="true"]`). Never style a bare `QFrame {}`.
  It matches every child frame, label and table inside it and produces nested boxes.
- Icons come from `src/ui/icons.py` (stroke SVG, recolored from tokens), not emoji.
- Add a dark theme by creating another `Theme` instance and calling
  `apply_theme(app, DARK)`. Views need no change.

## Migration status

Migrated: dashboard. Scoped (`card_style`) but still on the old shim: home,
timesheet list/detail, activities, settings, log view. Still hand-styled:
project cards, smart-log dialog, tables/input styles inside the list views.
Migrate a view by replacing its `setStyleSheet` calls with `label()`, `button()`,
`Card()` and spacing tokens.

## References

- [Styling Approaches for Qt Widgets](https://doc.qt.io/qt-6/qtwidgets-styling-approaches.html)
- [Dynamic Properties and Stylesheets](https://wiki.qt.io/DynamicPropertiesAndStylesheets)
- [Styling the Widgets Application (Qt for Python)](https://doc.qt.io/qtforpython/tutorials/basictutorial/widgetstyling.html)
- [Theming Guide: token layers (QTframework)](https://beelzer.github.io/QTframework/guides/theming.html)
