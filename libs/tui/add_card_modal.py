#!/usr/bin/env python

"""Search Scryfall and add copies of a card to the open deck or binder."""

import asyncio
import sys
from collections.abc import Callable
from functools import partial

try:
    from pymtgdeck import Binder, Deck
    from pyscryfall import (
        ScryfallApiError,
        ScryfallCard,
        autocomplete_card_name,
        search_cards_by_name,
    )
    from textual import on, work
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.screen import ModalScreen
    from textual.widgets import Button, Input, Label, ListItem, ListView, Static
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

from .formatting import format_scryfall_card


class SearchResultItem(ListItem):
    """A selectable row in the Scryfall search results list."""

    def __init__(self, card: ScryfallCard) -> None:
        self.card = card
        name = card.name or "(unnamed)"
        set_code = card.set or "?"
        cn = card.collector_number or "?"
        cmc = card.cmc if card.cmc is not None else "?"
        rarity = card.rarity or "?"
        price = f"${card.prices.usd}" if (card.prices and card.prices.usd) else "N/A"
        super().__init__(Label(f"{name}  [{set_code}] #{cn}  CMC:{cmc}  {rarity}  {price}"))


class AddCardModal(ModalScreen[None]):
    """Search Scryfall and add copies of a card to the open deck or binder."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=True),
    ]

    def __init__(
        self,
        collection: Deck | Binder,
        on_collection_changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self.collection = collection
        self._on_collection_changed = on_collection_changed
        self._autocomplete_timer = None

    def compose(self) -> ComposeResult:
        is_deck = isinstance(self.collection, Deck)
        title = "Add card to deck" if is_deck else "Add card to binder"
        add_label = "Add to deck" if is_deck else "Add to binder"
        with Vertical(id="add-card-dialog"):
            yield Label(title, classes="dialog-title")
            with Horizontal(id="search-row"):
                yield Input(placeholder="Card name…", id="card-name-input")
                yield Button("Search", id="search-btn", variant="primary")
            yield Static("", id="autocomplete-hints")
            yield Static("", id="search-status")
            yield Label("Matching prints (use ↑↓ to choose one):")
            yield ListView(id="search-results", initial_index=None)
            with Horizontal(id="add-row"):
                yield Label("Copies:", classes="label-text")
                yield Input(value="1", id="copy-count-input", classes="narrow-input")
                yield Button(add_label, id="add-btn", variant="success")
                yield Button("Close", id="close-btn", variant="warning")
            with VerticalScroll(id="preview-scroll"):
                yield Static("", id="preview-static")

    def on_mount(self) -> None:
        self.query_one("#card-name-input", Input).focus()

    # --- Autocomplete ---

    @on(Input.Changed, "#card-name-input")
    def card_name_changed(self, event: Input.Changed) -> None:
        if self._autocomplete_timer is not None:
            self._autocomplete_timer.stop()
            self._autocomplete_timer = None
        query = event.value.strip()
        if len(query) < 2:
            self.query_one("#autocomplete-hints", Static).update("")
            return
        self._autocomplete_timer = self.set_timer(
            0.3, partial(self._fetch_autocomplete, query)
        )

    @work
    async def _fetch_autocomplete(self, query: str) -> None:
        loop = asyncio.get_running_loop()
        try:
            catalog = await loop.run_in_executor(
                None, partial(autocomplete_card_name, query)
            )
            suggestions = catalog.data[:6]
            hints = self.query_one("#autocomplete-hints", Static)
            if suggestions:
                hints.update("[dim]" + "  |  ".join(suggestions) + "[/dim]")
            else:
                hints.update("")
        except Exception:
            pass

    # --- Search ---

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

    # --- Add card ---

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
        col = self.collection

        if isinstance(col, Deck):
            current = col.get_card_copy_count(card)
            room_copies = col.max_card_copy_count - current
            room_total = col.max_card_count - col.get_card_count()
            max_add = min(room_copies, room_total)
            if max_add <= 0:
                if room_total <= 0:
                    status.update("[red]Deck is full.[/red]")
                else:
                    status.update(
                        f"[red]Already have {current} copy/copies of this card "
                        f"(max {col.max_card_copy_count}).[/red]"
                    )
                return
            add_n = min(want, max_add)
        else:
            add_n = want

        try:
            col.add_card(card, add_n)
        except ValueError as exc:
            status.update(f"[red]{exc}[/red]")
            return

        if isinstance(col, Deck) and add_n < want:
            status.update(
                f"[yellow]Only {add_n} copy/copies fit "
                f"(deck limits); added that many.[/yellow]"
            )
        else:
            status.update(f"[green]Added {add_n}× {card.name or 'card'}.[/green]")

        if callable(self._on_collection_changed):
            self._on_collection_changed()

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
