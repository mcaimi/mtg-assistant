#!/usr/bin/env python

"""Import a deck from a pasted plain-text list."""

import asyncio
import sys
from functools import partial

try:
    from pymtgdeck import Deck, deck_from_text
    from textual import on, work
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.screen import ModalScreen
    from textual.widgets import Button, Label, Static, TextArea
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)


class ImportDeckModal(ModalScreen["Deck | None"]):
    """Paste a deck list and import each card from Scryfall.

    Format: one '[count] [card name]' per line. Lines starting with // are ignored.
    """

    BINDINGS = [
        Binding("escape", "close", "Cancel", show=True),
    ]

    def __init__(self, collection: Deck) -> None:
        super().__init__()
        self._collection = collection

    def compose(self) -> ComposeResult:
        with Vertical(id="import-dialog"):
            yield Label("Import deck from text", classes="dialog-title")
            yield Static(
                "Paste a deck list — one [bold]<count> <card name>[/bold] per line. "
                "Lines starting with [bold]//[/bold] are ignored. "
                "Each card is looked up on Scryfall (requires network access).",
                classes="dialog-hint",
            )
            yield TextArea(id="deck-text-input")
            yield Static("", id="import-status")
            with Horizontal(id="import-buttons"):
                yield Button("Import", id="import-confirm", variant="primary")
                yield Button("Cancel", id="import-cancel", variant="warning")

    def on_mount(self) -> None:
        self.query_one("#deck-text-input", TextArea).focus()

    @on(Button.Pressed, "#import-confirm")
    @work
    async def import_pressed(self) -> None:
        text = self.query_one("#deck-text-input", TextArea).text
        status = self.query_one("#import-status", Static)
        if not text.strip():
            status.update("[yellow]Paste a deck list first.[/yellow]")
            return
        status.update("[dim]Fetching cards from Scryfall…[/dim]")
        col = self._collection
        fresh = Deck(
            name=col.name,
            max_card_count=col.max_card_count,
            max_card_copy_count=col.max_card_copy_count,
        )
        loop = asyncio.get_running_loop()
        try:
            imported = await loop.run_in_executor(
                None, partial(deck_from_text, text, fresh)
            )
        except Exception as exc:
            status.update(f"[red]Import failed: {exc}[/red]")
            return
        self.dismiss(imported)

    @on(Button.Pressed, "#import-cancel")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)


__all__ = ["ImportDeckModal"]
