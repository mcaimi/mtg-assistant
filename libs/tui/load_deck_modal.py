#!/usr/bin/env python

from __future__ import annotations

import json
from pathlib import Path

from pymtgdeck import Deck
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, ListItem, ListView, Static


def load_deck_from_json_path(path: Path) -> Deck:
    """Load a ``Deck`` from either a bare ``Deck.to_dict()`` JSON or a ``Backend`` envelope."""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError("Deck file must contain a JSON object")
    if raw.get("type") == "Deck" and isinstance(raw.get("data"), dict):
        return Deck.from_dict(raw["data"])
    if raw.get("type") == "Binder":
        raise ValueError("File is a binder, not a deck")
    return Deck.from_dict(raw)


class DeckFileListItem(ListItem):
    """One row in the load-deck file list."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.load_error: str | None = None
        self.deck: Deck | None = None
        try:
            self.deck = load_deck_from_json_path(path)
            label_text = f"{self.deck.name}  —  {path.name}"
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            label_text = f"{path.name}  [invalid: {exc}]"
            self.load_error = str(exc)
        super().__init__(Label(label_text))


class LoadDeckModal(ModalScreen[Deck | None]):
    """Pick a ``*.json`` deck file from the decks directory and load it into the app."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=True),
    ]

    CSS = """
    LoadDeckModal {
        align: center middle;
    }
    #load-deck-dialog {
        width: 80;
        max-height: 90%;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #deck-files-list {
        height: 16;
        margin: 1 0;
    }
    .dialog-title {
        text-style: bold;
        margin-bottom: 1;
    }
    """

    def __init__(self, decks_directory: Path | str) -> None:
        super().__init__()
        self._decks_dir = Path(decks_directory)

    def compose(self) -> ComposeResult:
        with Vertical(id="load-deck-dialog"):
            yield Static("Load deck", classes="dialog-title")
            yield Static(
                "Choose a deck file (↑↓). [bold]Enter[/bold] loads it. [bold]Escape[/bold] closes.",
                classes="help",
            )
            paths = sorted(self._decks_dir.glob("*.json"))
            if not paths:
                yield Static(f"No .json files in [bold]{self._decks_dir}[/bold].", id="no-files")
            yield ListView(
                *[DeckFileListItem(p) for p in paths],
                id="deck-files-list",
                initial_index=0 if paths else None,
            )
            with Vertical(classes="button-row"):
                yield Button("Close", id="load-deck-close", variant="warning")

    def on_mount(self) -> None:
        lv = self.query_one("#deck-files-list", ListView)
        if lv.children:
            lv.focus()
        else:
            self.query_one("#load-deck-close", Button).focus()

    @on(ListView.Selected, "#deck-files-list")
    def deck_file_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if not isinstance(item, DeckFileListItem):
            return
        if item.deck is None:
            self.app.notify(
                f"Cannot load {item.path.name}: {item.load_error or 'unknown error'}",
                severity="error",
            )
            return
        self.dismiss(item.deck)

    @on(Button.Pressed, "#load-deck-close")
    def close_pressed(self) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)
