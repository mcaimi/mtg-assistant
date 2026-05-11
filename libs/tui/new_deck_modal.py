#!/usr/bin/env python

from __future__ import annotations

import json
import re
from pathlib import Path

from pymtgdeck import Deck
from pymtgdeck.entities.deck import MAX_CARD_COPY_COUNT, MAX_CARD_COUNT
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class NewDeckModal(ModalScreen[Deck | None]):
    """Create an empty deck with custom limits and save it under the decks directory."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=True),
    ]

    CSS = """
    NewDeckModal {
        align: center middle;
    }
    #new-deck-dialog {
        width: 72;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    .dialog-title {
        text-style: bold;
        margin-bottom: 1;
    }
    .field-row {
        height: auto;
        margin-bottom: 1;
    }
    .field-row Label {
        width: 26;
        content-align: left middle;
    }
    .field-row Input {
        width: 1fr;
    }
    #new-deck-status {
        margin: 1 0;
        min-height: 1;
    }
    #new-deck-buttons {
        height: auto;
        margin-top: 1;
    }
    """

    def __init__(self, decks_directory: Path | str) -> None:
        super().__init__()
        self._decks_dir = Path(decks_directory)

    def compose(self) -> ComposeResult:
        with Vertical(id="new-deck-dialog"):
            yield Label("New deck", classes="dialog-title")
            yield Static(
                "Set the deck [bold]name[/bold] and limits, then confirm. "
                "A JSON file is created in your decks folder.",
            )
            with Horizontal(classes="field-row"):
                yield Label("Name")
                yield Input(placeholder="Deck name", id="new-deck-name")
            with Horizontal(classes="field-row"):
                yield Label("Max cards in deck")
                yield Input(
                    value=str(MAX_CARD_COUNT),
                    id="new-deck-max-cards",
                    placeholder=str(MAX_CARD_COUNT),
                )
            with Horizontal(classes="field-row"):
                yield Label("Max copies per card")
                yield Input(
                    value=str(MAX_CARD_COPY_COUNT),
                    id="new-deck-max-copies",
                    placeholder=str(MAX_CARD_COPY_COUNT),
                )
            yield Static("", id="new-deck-status")
            with Horizontal(id="new-deck-buttons"):
                yield Button("Create deck", id="new-deck-confirm", variant="primary")
                yield Button("Cancel", id="new-deck-cancel", variant="warning")

    def on_mount(self) -> None:
        self.query_one("#new-deck-name", Input).focus()

    @staticmethod
    def _parse_positive_int(raw: str, field: str) -> int:
        text = raw.strip()
        if not text:
            raise ValueError(f"{field} is required")
        value = int(text)
        if value < 1:
            raise ValueError(f"{field} must be at least 1")
        return value

    @on(Button.Pressed, "#new-deck-confirm")
    def confirm_pressed(self) -> None:
        status = self.query_one("#new-deck-status", Static)
        name = self.query_one("#new-deck-name", Input).value.strip()
        if not name:
            status.update("[red]Please enter a deck name.[/red]")
            return
        try:
            max_cards = self._parse_positive_int(
                self.query_one("#new-deck-max-cards", Input).value,
                "Max cards in deck",
            )
            max_copies = self._parse_positive_int(
                self.query_one("#new-deck-max-copies", Input).value,
                "Max copies per card",
            )
        except ValueError as exc:
            status.update(f"[red]{exc}[/red]")
            return

        deck = Deck(
            max_card_copy_count=max_copies,
            max_card_count=max_cards,
            name=name,
        )

        self.app.notify(f"Created deck [bold]{name}[/bold]")
        self.dismiss(deck)

    @on(Button.Pressed, "#new-deck-cancel")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)
