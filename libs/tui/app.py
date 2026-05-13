#!/usr/bin/env python

# Main MTG Assistant TUI application class

import hashlib
import sys
from pathlib import Path
from typing import ClassVar

# import the necessary modules
try:
    from pymtgdeck import Backend, Binder, Deck, Entry
    from textual import on, work
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.widgets import (
        Footer,
        Header,
        Label,
        ListItem,
        ListView,
        ProgressBar,
        Static,
    )
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

# load local modules and classes
from .add_card_modal import AddCardModal
from .formatting import format_deck_entry
from .load_modal import LoadModal
from .create_modal import CreateModal


class DeckListItem(ListItem):
    """Selectable row for one entry (card + copy count) in the deck or binder."""

    def __init__(self, entry: Entry) -> None:
        self.entry = entry
        name = entry.card.name or "?"
        super().__init__(Label(f"{entry.count}× {name}"))


class MTGAssistantApp(App[None]):
    """Browser for decks or binders: list on the left, card details on the right; [a] adds cards
    via Scryfall. [n] creates a new deck. [s] saves the current deck or binder. [l] loads a saved
    deck or binder. [plus] / [minus] adjust copies of the selected card (deck rules apply to decks).
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("a", "add_card", "Add card", priority=True),
        Binding("n", "new_collection", "New collection", priority=True),
        Binding("s", "save_collection", "Save collection"),
        Binding("l", "load_collection", "Load collection"),
        Binding(
            "plus",
            "entry_add_copy",
            "+1 copy",
            key_display="+",
        ),
        Binding(
            "minus",
            "entry_remove_copy",
            "-1 copy",
            key_display="-",
        ),
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
    #right-pane-scroll {
        height: 1fr;
        min-height: 0;
    }
    .pane-title {
        text-style: bold;
        margin: 1 0;
    }
    #deck-list {
        height: 1fr;
    }
    #deck-size-footer {
        height: auto;
        margin-top: 1;
        padding-top: 1;
        border-top: solid $primary-darken-3;
        align-horizontal: right;
        width: 100%;
    }
    #deck-size-label {
        margin-bottom: 1;
        color: $text-muted;
        text-align: right;
        width: auto;
    }
    #deck-size-progress {
        width: 36;
        height: 1;
    }
    #entry-detail {
        height: 1fr;
    }
    """

    def __init__(
        self,
        deck: Deck | Binder,
        decks_directory: str,
        binders_directory: str,
        *,
        registry_root: str | Path | None = None,
    ) -> None:
        super().__init__()
        self.deck = deck
        self._decks_backend = Backend(decks_directory)
        self._binders_backend = Backend(binders_directory)
        self._registry_root = Path(registry_root) if registry_root else Path(decks_directory).parent

    def _backend_for(self) -> Backend:
        """Decks and binders are stored under separate asset directories."""
        return self._decks_backend if isinstance(self.deck, Deck) else self._binders_backend

    def _backend_save_path(self) -> Path:
        """Same filename rule as ``Backend.save`` (hash of collection ``name``)."""
        file_name = hashlib.sha256(self.deck.name.encode()).hexdigest() + ".json"
        return self._backend_for().file_path / file_name

    def _current_deck_list_row(self) -> DeckListItem | None:
        """Highlighted deck row, only when no modal or pushed screen is above the main UI."""
        if len(self.screen_stack) > 1:
            return None
        deck_list = self.query_one("#deck-list", ListView)
        item = deck_list.highlighted_child
        return item if isinstance(item, DeckListItem) else None

    def action_entry_add_copy(self) -> None:
        row = self._current_deck_list_row()
        if row is None:
            return
        try:
            self.deck.add_card(row.entry.card, 1)
        except ValueError as exc:
            self.notify(str(exc), severity="warning")
            return
        self._reload_collection_ui(reset_highlight=False)

    def action_entry_remove_copy(self) -> None:
        row = self._current_deck_list_row()
        if row is None:
            return
        try:
            self.deck.remove_card(row.entry.card, 1)
        except ValueError as exc:
            self.notify(str(exc), severity="warning")
            return
        self._reload_collection_ui(reset_highlight=False)

    def on_mount(self) -> None:
        self.title = "MTG Assistant"
        self.sub_title = self.deck.name
        deck_list = self.query_one("#deck-list", ListView)
        deck_list.focus()
        self._update_deck_size_indicator()

    def _update_deck_size_indicator(self) -> None:
        bar = self.query_one("#deck-size-progress", ProgressBar)
        label = self.query_one("#deck-size-label", Static)
        if isinstance(self.deck, Deck):
            current = self.deck.get_card_count()
            limit = self.deck.max_card_count
            bar.update(total=float(limit), progress=float(current))
            label.update(f"{current} / {limit} cards")
        else:
            total = sum(e.count for e in self.deck.entries)
            bar.update(total=1.0, progress=1.0 if total else 0.0)
            label.update(f"{total} cards (binder)")

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-row"):
            with Vertical(id="left-pane"):
                kind = "Deck" if isinstance(self.deck, Deck) else "Binder"
                yield Static(kind, classes="pane-title", id="collection-pane-title")
                yield ListView(
                    *[DeckListItem(e) for e in self.deck.entries],
                    id="deck-list",
                    initial_index=0 if self.deck.entries else None,
                )
            with Vertical(id="right-pane"):
                with VerticalScroll(id="right-pane-scroll"):
                    yield Static("Selected card", classes="pane-title")
                    yield Static(self._empty_detail_text(), id="entry-detail")
                with Vertical(id="deck-size-footer"):
                    yield Static("", id="deck-size-label")
                    yield ProgressBar(
                        id="deck-size-progress",
                        total=float(self.deck.max_card_count)
                        if isinstance(self.deck, Deck)
                        else 1.0,
                        show_eta=False,
                        show_percentage=False,
                    )
        yield Footer()

    def _empty_detail_text(self) -> str:
        if self.deck.entries:
            return format_deck_entry(self.deck.entries[0])
        return (
            "No cards yet.\n\n"
            "Use [bold]a[/bold] to open the add-card dialog, search Scryfall, "
            "pick a print, set the number of copies, and add to this collection."
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
        self.push_screen(AddCardModal(self.deck, self.notify_collection_changed))

    def action_save_collection(self) -> None:
        path = self._backend_save_path()
        if path.exists():
            path.unlink()
        try:
            file_name = self._backend_for().save(self.deck)
        except OSError as exc:
            self.notify(f"Could not save: {exc}", severity="error")
            return
        backend = self._backend_for()
        self.notify(f"Saved to {backend.file_path / file_name}")

    def action_load_collection(self) -> None:
        self.push_screen(LoadModal(self._registry_root), self._on_collection_loaded)

    def action_new_collection(self) -> None:
        self.push_screen(CreateModal(self._decks_backend.file_path), self._on_new_collection_created)

    def _on_new_collection_created(self, created: Deck | Binder | None) -> None:
        if created is None:
            return
        self.deck = created
        self.notify_collection_changed()

    def _on_collection_loaded(self, loaded: Deck | Binder | None) -> None:
        if loaded is None:
            return
        self.deck = loaded
        self.notify_collection_changed()

    def notify_collection_changed(self) -> None:
        self._reload_collection_ui()

    @work
    async def _reload_collection_ui(self, *, reset_highlight: bool = True) -> None:
        deck_list = self.query_one("#deck-list", ListView)
        detail = self.query_one("#entry-detail", Static)
        pane_title = self.query_one("#collection-pane-title", Static)
        pane_title.update("Deck" if isinstance(self.deck, Deck) else "Binder")
        previous_index = deck_list.index
        await deck_list.query("ListItem").remove()
        if not self.deck.entries:
            deck_list.index = None
            detail.update(self._empty_detail_text())
            self.sub_title = self.deck.name
            self._update_deck_size_indicator()
            return
        await deck_list.extend(DeckListItem(e) for e in self.deck.entries)
        n = len(self.deck.entries)
        if reset_highlight or previous_index is None:
            deck_list.index = 0
        else:
            deck_list.index = min(previous_index, n - 1)
        highlighted = deck_list.highlighted_child
        if isinstance(highlighted, DeckListItem):
            detail.update(format_deck_entry(highlighted.entry))
        else:
            detail.update(self._empty_detail_text())
        self.sub_title = self.deck.name
        self._update_deck_size_indicator()


__all__ = ["MTGAssistantApp"]
