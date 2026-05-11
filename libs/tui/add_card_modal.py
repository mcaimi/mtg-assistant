#!/usr/bin/env python

from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import partial

from pymtgdeck import Deck
from pyscryfall import ScryfallApiError, ScryfallCard, search_cards_by_name
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from .formatting import format_scryfall_card


class SearchResultItem(ListItem):
    """A selectable row in the Scryfall search results list."""

    def __init__(self, card: ScryfallCard) -> None:
        self.card = card
        name = card.name or "(unnamed)"
        set_code = card.set or "?"
        cn = card.collector_number or "?"
        rarity = card.rarity or "?"
        super().__init__(Label(f"{name}  [{set_code}] #{cn}  {rarity}"))


class AddCardModal(ModalScreen[None]):
    """Search Scryfall and add copies of a card to the open deck."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=True),
    ]

    CSS = """
    AddCardModal {
        align: center middle;
    }
    #add-card-dialog {
        width: 88;
        max-height: 90%;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #search-row {
        height: auto;
        margin-bottom: 1;
    }
    #card-name-input {
        width: 1fr;
        margin-right: 1;
    }
    #search-results {
        height: 12;
        margin: 1 0;
    }
    .narrow-input {
        width: 8;
    }
    .dialog-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #preview-scroll {
        max-height: 14;
        margin-top: 1;
    }
    """

    def __init__(self, deck: Deck, on_deck_changed: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.deck = deck
        self._on_deck_changed = on_deck_changed

    def compose(self) -> ComposeResult:
        with Vertical(id="add-card-dialog"):
            yield Label("Add card to deck", classes="dialog-title")
            with Horizontal(id="search-row"):
                yield Input(placeholder="Card name…", id="card-name-input")
                yield Button("Search", id="search-btn", variant="primary")
            yield Static("", id="search-status")
            yield Label("Matching prints (use ↑↓ to choose one):")
            yield ListView(id="search-results", initial_index=None)
            with Horizontal(id="add-row"):
                yield Label("Copies:")
                yield Input(value="1", id="copy-count-input", classes="narrow-input")
                yield Button("Add to deck", id="add-btn", variant="success")
                yield Button("Close", id="close-btn", variant="warning")
            with VerticalScroll(id="preview-scroll"):
                yield Static("", id="preview-static")

    def on_mount(self) -> None:
        self.query_one("#card-name-input", Input).focus()

    @on(Button.Pressed, "#search-btn")
    async def search_pressed(self) -> None:
        query = self.query_one("#card-name-input", Input).value.strip()
        status = self.query_one("#search-status", Static)
        results = self.query_one("#search-results", ListView)
        preview = self.query_one("#preview-static", Static)

        preview.update("")
        if not query:
            status.update("[yellow]Enter a card name first.[/yellow]")
            return

        status.update("[dim]Searching Scryfall…[/dim]")
        loop = asyncio.get_running_loop()
        try:
            listing = await loop.run_in_executor(
                None, partial(search_cards_by_name, query)
            )
        except ScryfallApiError as exc:
            status.update(f"[red]Search failed: {exc}[/red]")
            await results.query("ListItem").remove()
            return

        cards = listing.data
        if not cards:
            status.update("[yellow]No cards matched that name.[/yellow]")
            await results.query("ListItem").remove()
            return

        status.update(f"[green]{len(cards)} print(s) found[/green] (total {listing.total_cards})")
        await results.query("ListItem").remove()
        await results.extend(SearchResultItem(c) for c in cards)
        results.index = 0

    @on(Button.Pressed, "#add-btn")
    def add_pressed(self) -> None:
        status = self.query_one("#search-status", Static)
        results = self.query_one("#search-results", ListView)
        highlighted = results.highlighted_child
        if not isinstance(highlighted, SearchResultItem):
            status.update("[yellow]Select a print from the list first.[/yellow]")
            return

        raw = self.query_one("#copy-count-input", Input).value.strip() or "1"
        try:
            want = int(raw)
        except ValueError:
            status.update("[red]Copies must be a whole number.[/red]")
            return
        if want < 1:
            status.update("[red]Add at least one copy.[/red]")
            return

        card = highlighted.card
        current = self.deck.get_card_copy_count(card)
        room_copies = self.deck.max_card_copy_count - current
        room_total = self.deck.max_card_count - self.deck.get_card_count()
        max_add = min(room_copies, room_total)
        if max_add <= 0:
            if room_total <= 0:
                status.update("[red]Deck is full.[/red]")
            else:
                status.update(
                    f"[red]Already have {current} copy/copies of this card "
                    f"(max {self.deck.max_card_copy_count}).[/red]"
                )
            return

        add_n = min(want, max_add)
        if add_n < want:
            status.update(
                f"[yellow]Only {add_n} copy/copies fit "
                f"(deck limits); added that many.[/yellow]"
            )
        else:
            status.update(f"[green]Added {add_n}× {card.name or 'card'}.[/green]")

        try:
            self.deck.add_card(card, add_n)
        except ValueError as exc:
            status.update(f"[red]{exc}[/red]")
            return

        if callable(self._on_deck_changed):
            self._on_deck_changed()

    @on(Button.Pressed, "#close-btn")
    def close_pressed(self) -> None:
        self.dismiss()

    def action_close(self) -> None:
        self.dismiss()

    @on(ListView.Highlighted, "#search-results")
    def result_highlighted(self, event: ListView.Highlighted) -> None:
        preview = self.query_one("#preview-static", Static)
        item = event.item
        if isinstance(item, SearchResultItem):
            preview.update(format_scryfall_card(item.card))
        else:
            preview.update("")
