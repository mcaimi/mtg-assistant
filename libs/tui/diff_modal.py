#!/usr/bin/env python

"""Compare the current deck/binder against another saved collection."""

import json
import sys
from pathlib import Path

try:
    from pymtgdeck import Binder, Deck, Registry, Sideboard, deck_diff
    from textual import on
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.screen import ModalScreen
    from textual.widgets import Button, Label, ListItem, ListView, Static
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)


def _load_from_path(path: Path) -> Deck | Binder:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    kind = raw.get("type")
    data = raw.get("data")
    if kind == "Deck" and isinstance(data, dict):
        return Deck.from_dict(data)
    if kind == "Sideboard" and isinstance(data, dict):
        return Sideboard.from_dict(data)
    if kind == "Binder" and isinstance(data, dict):
        return Binder.from_dict(data)
    raise ValueError(f"Unsupported collection type: {kind!r}")


class _RegistryItem(ListItem):
    def __init__(self, entry: dict) -> None:
        self.reg_entry = entry
        kind = entry.get("type", "?")
        name = entry.get("name", Path(str(entry.get("path", "?"))).name)
        super().__init__(Label(f"[{kind}] {name}"))


class DeckDiffModal(ModalScreen[None]):
    """Select a saved collection and compare it against the current one using deck_diff."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=True),
    ]

    def __init__(self, collection: Deck | Binder, registry_root: Path | str) -> None:
        super().__init__()
        self._collection = collection
        self._registry_root = Path(registry_root)

    def _registry_entries(self) -> list[dict]:
        try:
            reg = Registry(str(self._registry_root))
        except Exception:
            return []
        return sorted(
            reg.registry,
            key=lambda e: (str(e.get("type", "")), str(e.get("name", "")).lower()),
        )

    def compose(self) -> ComposeResult:
        current_name = self._collection.name
        entries = self._registry_entries()
        with Vertical(id="diff-dialog"):
            yield Label("Compare decks", classes="dialog-title")
            yield Static(
                f"Current: [bold]{current_name}[/bold]. "
                "Select another collection and press [bold]Enter[/bold] to diff.",
                classes="dialog-hint",
            )
            if entries:
                yield ListView(
                    *[_RegistryItem(e) for e in entries],
                    id="diff-select-list",
                    initial_index=0,
                )
            else:
                yield Static("[dim]No saved collections found.[/dim]", id="diff-select-list")
            with VerticalScroll(id="diff-results"):
                yield Static("", id="diff-added")
                yield Static("", id="diff-removed")
                yield Static("", id="diff-changed")
            with Horizontal(id="diff-buttons"):
                yield Button("Close", id="diff-close", variant="warning")

    def on_mount(self) -> None:
        try:
            lv = self.query_one("#diff-select-list", ListView)
            lv.focus()
        except Exception:
            pass

    @on(ListView.Selected, "#diff-select-list")
    def collection_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if not isinstance(item, _RegistryItem):
            return
        path = Path(str(item.reg_entry.get("path", "")))
        try:
            other = _load_from_path(path)
        except Exception as exc:
            self.app.notify(f"Could not load: {exc}", severity="error")
            return
        self._show_diff(other)

    def _show_diff(self, other: Deck | Binder) -> None:
        result = deck_diff(self._collection, other)
        other_name = other.name

        added = result.get("added", [])
        removed = result.get("removed", [])
        changed = result.get("changed", [])

        added_widget = self.query_one("#diff-added", Static)
        removed_widget = self.query_one("#diff-removed", Static)
        changed_widget = self.query_one("#diff-changed", Static)
        results_panel = self.query_one("#diff-results", VerticalScroll)

        if added:
            lines = [f"[bold green]+ Added in {other_name}:[/bold green]"]
            for e in added:
                lines.append(f"  + {e.count}× {e.card.name or '?'}")
            added_widget.update("\n".join(lines))
        else:
            added_widget.update(f"[dim]No cards added in {other_name}.[/dim]")

        if removed:
            lines = [f"[bold red]− Removed from {other_name}:[/bold red]"]
            for e in removed:
                lines.append(f"  − {e.count}× {e.card.name or '?'}")
            removed_widget.update("\n".join(lines))
        else:
            removed_widget.update(f"[dim]No cards removed in {other_name}.[/dim]")

        if changed:
            lines = [f"[bold yellow]~ Changed counts:[/bold yellow]"]
            for c in changed:
                lines.append(f"  ~ {c['card']}: {c['from']}→{c['to']}")
            changed_widget.update("\n".join(lines))
        else:
            changed_widget.update("[dim]No count changes.[/dim]")

        results_panel.display = True

    @on(Button.Pressed, "#diff-close")
    def close_pressed(self) -> None:
        self.dismiss()

    def action_close(self) -> None:
        self.dismiss()


__all__ = ["DeckDiffModal"]
