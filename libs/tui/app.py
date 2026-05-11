#!/usr/bin/env python

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import ClassVar

try:
    from pymtgdeck import Backend, Deck, Entry
    from textual import on, work
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.widgets import Footer, Header, Label, ListItem, ListView, Static
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

from .add_card_modal import AddCardModal
from .formatting import format_deck_entry
from .load_deck_modal import LoadDeckModal


class DeckListItem(ListItem):
    """Selectable row for one deck entry (card + copy count)."""

    def __init__(self, entry: Entry) -> None:
        self.entry = entry
        name = entry.card.name or "?"
        super().__init__(Label(f"{entry.count}× {name}"))


class MTGAssistantApp(App[None]):
    """Deck browser: list on the left, card details on the right; [a] adds cards via Scryfall."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("a", "add_card", "Add card", priority=True),
        Binding("s", "save_deck", "Save deck"),
        Binding("l", "load_deck", "Load deck"),
    ]

    CSS = """
    #main-row {
        height: 1fr;
    }
    #left-pane {
        width: 38%;
        min-width: 24;
        height: 1fr;
        border: tall $primary-darken-2;
        padding: 0 1;
    }
    #right-pane {
        width: 1fr;
        height: 1fr;
        border: tall $primary-darken-2;
        padding: 0 1;
    }
    .pane-title {
        text-style: bold;
        margin: 1 0;
    }
    #deck-list {
        height: 1fr;
    }
    #entry-detail {
        height: 1fr;
    }
    """

    def __init__(self, deck: Deck, decks_directory: str) -> None:
        super().__init__()
        self.deck = deck
        self._backend = Backend(decks_directory)

    def _backend_save_path(self) -> Path:
        """Same filename rule as ``Backend.save`` (hash of deck ``name``)."""
        file_name = hashlib.sha256(self.deck.name.encode()).hexdigest() + ".json"
        return self._backend.file_path / file_name

    def on_mount(self) -> None:
        self.title = "MTG Assistant"
        self.sub_title = self.deck.name
        deck_list = self.query_one("#deck-list", ListView)
        deck_list.focus()

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-row"):
            with Vertical(id="left-pane"):
                yield Static("Deck", classes="pane-title")
                yield ListView(
                    *[DeckListItem(e) for e in self.deck.entries],
                    id="deck-list",
                    initial_index=0 if self.deck.entries else None,
                )
            with VerticalScroll(id="right-pane"):
                yield Static("Selected card", classes="pane-title")
                yield Static(self._empty_detail_text(), id="entry-detail")
        yield Footer()

    def _empty_detail_text(self) -> str:
        if self.deck.entries:
            return format_deck_entry(self.deck.entries[0])
        return (
            "Deck is empty.\n\n"
            "Use [bold]a[/bold] to open the add-card dialog, search Scryfall, "
            "pick a print, set the number of copies, and add to this deck."
        )

    @on(ListView.Highlighted, "#deck-list")
    def deck_row_highlighted(self, event: ListView.Highlighted) -> None:
        detail = self.query_one("#entry-detail", Static)
        item = event.item
        if isinstance(item, DeckListItem):
            detail.update(format_deck_entry(item.entry))
        else:
            detail.update(self._empty_detail_text())

    def action_add_card(self) -> None:
        self.push_screen(AddCardModal(self.deck, self.notify_deck_changed))

    def action_save_deck(self) -> None:
        path = self._backend_save_path()
        if path.exists():
            path.unlink()
        try:
            file_name = self._backend.save(self.deck)
        except OSError as exc:
            self.notify(f"Could not save deck: {exc}", severity="error")
            return
        self.notify(f"Deck saved to {self._backend.file_path / file_name}")

    def action_load_deck(self) -> None:
        self.push_screen(LoadDeckModal(self._backend.file_path), self._on_deck_loaded)

    def _on_deck_loaded(self, deck: Deck | None) -> None:
        if deck is None:
            return
        self.deck = deck
        self.notify_deck_changed()

    def notify_deck_changed(self) -> None:
        self._reload_deck_ui()

    @work
    async def _reload_deck_ui(self) -> None:
        deck_list = self.query_one("#deck-list", ListView)
        detail = self.query_one("#entry-detail", Static)
        await deck_list.query("ListItem").remove()
        if not self.deck.entries:
            deck_list.index = None
            detail.update(self._empty_detail_text())
            self.sub_title = self.deck.name
            return
        await deck_list.extend(DeckListItem(e) for e in self.deck.entries)
        deck_list.index = 0
        highlighted = deck_list.highlighted_child
        if isinstance(highlighted, DeckListItem):
            detail.update(format_deck_entry(highlighted.entry))
        self.sub_title = self.deck.name


__all__ = ["MTGAssistantApp"]
