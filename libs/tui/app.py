#!/usr/bin/env python

# Main MTG Assistant TUI application class

import hashlib
import sys
from pathlib import Path
from typing import ClassVar

_LOGO_PATH = Path(__file__).resolve().parent / "logo.utf8"


def _load_logo_banner():
    """ASCII art logo from ``logo.utf8`` (ANSI colors), or empty if missing."""
    from rich.text import Text

    try:
        return Text.from_ansi(_LOGO_PATH.read_text(encoding="utf-8").rstrip("\n"))
    except OSError:
        return ""


try:
    from pymtgdeck import (
        Backend,
        Binder,
        Deck,
        Entry,
        Sideboard,
        deck_average_cmc,
        deck_cmc_histogram,
        deck_color_distribution,
        deck_max_cmc,
        deck_min_cmc,
        deck_to_text,
        deck_type_distribution,
        mana_base_analysis,
        validate_legality,
    )
    from textual import on, work
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.widgets import (
        Footer,
        Header,
        Input,
        Label,
        ListItem,
        ListView,
        ProgressBar,
        Static,
    )
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

from .add_card_modal import AddCardModal
from .create_modal import CreateModal
from .diff_modal import DeckDiffModal
from .formatting import format_deck_entry
from .import_modal import ImportDeckModal
from .load_modal import LoadModal
from .rulings_modal import RulingsModal

_LEGALITY_FORMATS = [
    ("standard",  "Standard"),
    ("pioneer",   "Pioneer"),
    ("modern",    "Modern"),
    ("legacy",    "Legacy"),
    ("commander", "Commander"),
    ("vintage",   "Vintage"),
]


class DeckListItem(ListItem):
    """Selectable row for one entry (card + copy count) in the deck or binder."""

    def __init__(self, entry: Entry) -> None:
        self.entry = entry
        name = entry.card.name or "?"
        super().__init__(Label(f"{entry.count}× {name}"))


class MTGAssistantApp(App[None]):
    """Browser for decks, sideboards, and binders.

    [a] add card  [n] new  [s] save  [l] load  [i] import  [e] export
    [r] rulings  [c] compare  [f] legality  [/] filter  [+]/[-] copies
    """

    CSS_PATH = "app.tcss"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("a", "add_card", "Add card", priority=True),
        Binding("n", "new_collection", "New", priority=True),
        Binding("s", "save_collection", "Save"),
        Binding("l", "load_collection", "Load"),
        Binding("i", "import_deck", "Import"),
        Binding("e", "export_deck", "Export"),
        Binding("r", "show_rulings", "Rulings"),
        Binding("c", "compare_decks", "Compare"),
        Binding("f", "toggle_legality", "Legality"),
        Binding("slash", "focus_filter", "Filter", key_display="/"),
        Binding("plus",  "entry_add_copy",    "+1 copy", key_display="+"),
        Binding("minus", "entry_remove_copy", "-1 copy", key_display="-"),
    ]

    def __init__(
        self,
        collection: Deck | Binder,
        decks_directory: str,
        binders_directory: str,
        *,
        registry_root: str | Path | None = None,
    ) -> None:
        super().__init__()
        self.collection = collection
        self._decks_backend = Backend(decks_directory)
        self._binders_backend = Backend(binders_directory)
        self._registry_root = (
            Path(registry_root) if registry_root else Path(decks_directory).parent
        )
        self._is_dirty: bool = False
        self._filter_text: str = ""
        self._last_mana_warnings: frozenset[str] = frozenset()

    # --- Collection kind label ---

    def _collection_kind_label(self) -> str:
        if isinstance(self.collection, Sideboard):
            return "Sideboard"
        if isinstance(self.collection, Deck):
            return "Deck"
        return "Binder"

    # --- Subtitle / dirty flag ---

    def _update_subtitle(self) -> None:
        name = self.collection.name
        self.sub_title = f"* {name}" if self._is_dirty else name

    def _mark_dirty(self) -> None:
        self._is_dirty = True
        self._update_subtitle()

    def _mark_clean(self) -> None:
        self._is_dirty = False
        self._update_subtitle()

    def _replace_collection(self, new_collection: Deck | Binder) -> None:
        """Switch to a newly loaded/created collection; clears dirty flag and resets state."""
        self.collection = new_collection
        self._filter_text = ""
        self._last_mana_warnings = frozenset()
        self.query_one("#filter-input", Input).value = ""
        self._mark_clean()
        self._check_mana_base()
        self._reload_collection_ui()

    # --- Backend helpers ---

    def _backend_for(self) -> Backend:
        return self._decks_backend if isinstance(self.collection, Deck) else self._binders_backend

    def _backend_save_path(self) -> Path:
        file_name = hashlib.sha256(self.collection.name.encode()).hexdigest() + ".json"
        return self._backend_for().file_path / file_name

    def _current_collection_list_row(self) -> DeckListItem | None:
        if len(self.screen_stack) > 1:
            return None
        collection_list = self.query_one("#collection-list", ListView)
        item = collection_list.highlighted_child
        return item if isinstance(item, DeckListItem) else None

    # --- Copy +/- actions ---

    def action_entry_add_copy(self) -> None:
        row = self._current_collection_list_row()
        if row is None:
            return
        try:
            self.collection.add_card(row.entry.card, 1)
        except ValueError as exc:
            self.notify(str(exc), severity="warning")
            return
        self._mark_dirty()
        self._reload_collection_ui(reset_highlight=False)

    def action_entry_remove_copy(self) -> None:
        row = self._current_collection_list_row()
        if row is None:
            return
        try:
            self.collection.remove_card(row.entry.card, 1)
        except ValueError as exc:
            self.notify(str(exc), severity="warning")
            return
        self._mark_dirty()
        self._reload_collection_ui(reset_highlight=False)

    # --- Mount ---

    def on_mount(self) -> None:
        self.title = "MTG Assistant"
        self._update_subtitle()
        self.query_one("#collection-list", ListView).focus()
        self._update_analytics()

    # --- Filter ---

    def action_focus_filter(self) -> None:
        self.query_one("#filter-input", Input).focus()

    @on(Input.Changed, "#filter-input")
    def filter_changed(self, event: Input.Changed) -> None:
        self._filter_text = event.value.strip()
        self._reload_collection_ui(reset_highlight=True)

    def on_key(self, event) -> None:
        filter_input = self.query_one("#filter-input", Input)
        if event.key == "escape" and filter_input.has_focus:
            filter_input.value = ""
            self._filter_text = ""
            self.query_one("#collection-list", ListView).focus()
            event.stop()

    # --- Mana base warnings ---

    def _check_mana_base(self) -> None:
        if not isinstance(self.collection, Deck) or not self.collection.entries:
            self._last_mana_warnings = frozenset()
            return
        try:
            result = mana_base_analysis(self.collection)
            current_warnings = frozenset(result.get("warnings", []))
        except Exception:
            return
        new_warnings = current_warnings - self._last_mana_warnings
        self._last_mana_warnings = current_warnings
        for warning in sorted(new_warnings):
            self.notify(f"Mana base: {warning}", severity="warning", timeout=8)

    # --- Analytics rendering ---

    _MANA_CURVE_MAX_HEIGHT = 8

    def _render_mana_curve(self) -> str:
        if not isinstance(self.collection, Deck) or not self.collection.entries:
            return "[dim]No data[/dim]"
        counts, edges = deck_cmc_histogram(self.collection)
        int_counts = [int(c) for c in counts]
        max_c = max(int_counts, default=0)
        if max_c == 0:
            return "[dim]No data[/dim]"
        n = len(int_counts)
        display_h = min(max_c, self._MANA_CURVE_MAX_HEIGHT)
        scale = max_c / display_h
        lines: list[str] = []
        for level in range(display_h, 0, -1):
            threshold = level * scale
            row = " ".join("██" if c >= threshold else "  " for c in int_counts)
            lines.append(row)
        lines.append("──" + "───" * (n - 1))
        lines.append(" ".join(f"{int(edges[i]):>2}" for i in range(n)))
        lines.append(" ".join(f"[bold]{c:>2}[/bold]" for c in int_counts))
        return "\n".join(lines)

    def _render_cmc_stats(self) -> str:
        if not isinstance(self.collection, Deck) or not self.collection.entries:
            return ""
        try:
            avg = deck_average_cmc(self.collection)
            mn = deck_min_cmc(self.collection)
            mx = deck_max_cmc(self.collection)
            return f"Avg CMC: {avg:.1f}  Min: {int(mn)}  Max: {int(mx)}"
        except Exception:
            return ""

    def _render_type_distribution(self) -> str:
        if not self.collection.entries:
            return ""
        try:
            dist = deck_type_distribution(self.collection)
            total = max(sum(dist.values()), 1)
            parts = []
            for card_type, count in sorted(dist.items(), key=lambda x: -x[1]):
                if count == 0:
                    continue
                bar_len = max(1, round(count / total * 8))
                parts.append(f"[bold]{card_type[:3]}[/bold] {'█' * bar_len} {count}")
            return "  ".join(parts) if parts else ""
        except Exception:
            return ""

    def _render_color_distribution(self) -> str:
        if not self.collection.entries:
            return ""
        try:
            dist = deck_color_distribution(self.collection)
            total = max(sum(dist.values()), 1)
            if total == 0:
                return ""
            COLOR_MARKUP = {
                "W": "bold", "U": "bold blue", "B": "dim", "R": "bold red", "G": "bold green",
            }
            parts = []
            for color in ["W", "U", "B", "R", "G"]:
                count = dist.get(color, 0)
                if count == 0:
                    continue
                bar_len = max(1, round(count / total * 6))
                markup = COLOR_MARKUP.get(color, "bold")
                parts.append(f"[{markup}]{color}[/{markup}] {'█' * bar_len} {count}")
            return "  ".join(parts) if parts else ""
        except Exception:
            return ""

    def _render_legality(self) -> str:
        if not isinstance(self.collection, Deck) or not self.collection.entries:
            return "[dim]Load a deck to check legality.[/dim]"
        parts = []
        for fmt_key, fmt_label in _LEGALITY_FORMATS:
            try:
                illegal = validate_legality(self.collection, fmt_key)
            except ValueError:
                continue
            if not illegal:
                parts.append(f"[green]✓ {fmt_label}[/green]")
            else:
                parts.append(f"[red]✗ {fmt_label} ({len(illegal)})[/red]")
        return "  ".join(parts) if parts else "[dim]No legality data.[/dim]"

    def _render_deck_value(self) -> str:
        total = 0.0
        has_price = False
        for entry in self.collection.entries:
            if entry.card.prices and entry.card.prices.usd:
                try:
                    total += entry.count * float(entry.card.prices.usd)
                    has_price = True
                except ValueError:
                    pass
        return f"Est. value: [bold]${total:.2f}[/bold]" if has_price else ""

    # --- Analytics update methods ---

    def _update_mana_curve(self) -> None:
        self.query_one("#mana-curve-chart", Static).update(self._render_mana_curve())

    def _update_cmc_stats(self) -> None:
        self.query_one("#cmc-stats", Static).update(self._render_cmc_stats())

    def _update_type_color_distribution(self) -> None:
        self.query_one("#type-distribution", Static).update(self._render_type_distribution())
        self.query_one("#color-distribution", Static).update(self._render_color_distribution())

    def _update_legality(self) -> None:
        self.query_one("#legality-content", Static).update(self._render_legality())

    def _update_deck_value(self) -> None:
        self.query_one("#deck-value-label", Static).update(self._render_deck_value())

    def _update_collection_size_indicator(self) -> None:
        bar = self.query_one("#collection-size-progress", ProgressBar)
        label = self.query_one("#collection-size-label", Static)
        if isinstance(self.collection, Deck):
            current = self.collection.get_card_count()
            limit = self.collection.max_card_count
            bar.update(total=float(limit), progress=float(current))
            label.update(f"{current} / {limit} cards")
        else:
            total = sum(e.count for e in self.collection.entries)
            bar.update(total=1.0, progress=1.0 if total else 0.0)
            label.update(f"{total} cards (binder)")

    def _update_analytics(self) -> None:
        self._update_mana_curve()
        self._update_cmc_stats()
        self._update_type_color_distribution()
        self._update_collection_size_indicator()
        self._update_deck_value()
        if self.query_one("#legality-panel", Vertical).display:
            self._update_legality()

    # --- Layout ---

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(_load_logo_banner(), id="app-banner", markup=False)
        with Horizontal(id="main-row"):
            with Vertical(id="left-pane"):
                yield Static(
                    self._collection_kind_label(),
                    classes="pane-title",
                    id="collection-pane-title",
                )
                yield Input(
                    placeholder="Filter by name… (/ to focus, Esc to clear)",
                    id="filter-input",
                )
                yield ListView(
                    *[DeckListItem(e) for e in self.collection.entries],
                    id="collection-list",
                    initial_index=0 if self.collection.entries else None,
                )
            with Vertical(id="right-pane"):
                with VerticalScroll(id="right-pane-scroll"):
                    yield Static("Selected card", classes="pane-title")
                    yield Static(self._empty_detail_text(), id="entry-detail")
                with Vertical(id="mana-curve"):
                    yield Static("", id="cmc-stats")
                    yield Static("Mana Curve", id="mana-curve-title")
                    yield Static(self._render_mana_curve(), id="mana-curve-chart")
                with Vertical(id="type-color-dist"):
                    yield Static("", id="type-distribution")
                    yield Static("", id="color-distribution")
                with Vertical(id="legality-panel"):
                    yield Static("", id="legality-content")
                with Vertical(id="collection-size-footer"):
                    yield Static("", id="deck-value-label")
                    yield Static("", id="collection-size-label")
                    yield ProgressBar(
                        id="collection-size-progress",
                        total=float(self.collection.max_card_count)
                        if isinstance(self.collection, Deck)
                        else 1.0,
                        show_eta=False,
                        show_percentage=False,
                    )
        yield Footer()

    def _empty_detail_text(self) -> str:
        if self.collection.entries:
            return format_deck_entry(self.collection.entries[0])
        return (
            "No cards yet.\n\n"
            "Use [bold]a[/bold] to open the add-card dialog, search Scryfall, "
            "pick a print, set the number of copies, and add to this collection."
        )

    # --- Events ---

    @on(ListView.Highlighted, "#collection-list")
    def collection_row_highlighted(self, event: ListView.Highlighted) -> None:
        detail = self.query_one("#entry-detail", Static)
        item = event.item
        if isinstance(item, DeckListItem):
            detail.update(format_deck_entry(item.entry))
        else:
            detail.update(self._empty_detail_text())

    # --- Actions ---

    def action_add_card(self) -> None:
        self.push_screen(AddCardModal(self.collection, self.notify_collection_changed))

    def action_save_collection(self) -> None:
        path = self._backend_save_path()
        if path.exists():
            path.unlink()
        try:
            file_name = self._backend_for().save(self.collection)
        except OSError as exc:
            self.notify(f"Could not save: {exc}", severity="error")
            return
        self._mark_clean()
        self.notify(f"Saved {self.collection.name}")

    def action_load_collection(self) -> None:
        self.push_screen(LoadModal(self._registry_root), self._on_collection_loaded)

    def action_new_collection(self) -> None:
        self.push_screen(
            CreateModal(self._decks_backend.file_path), self._on_new_collection_created
        )

    def action_import_deck(self) -> None:
        if not isinstance(self.collection, Deck):
            self.notify("Import is only available for decks and sideboards.", severity="warning")
            return
        self.push_screen(ImportDeckModal(self.collection), self._on_deck_imported)

    def action_export_deck(self) -> None:
        if not self.collection.entries:
            self.notify("Nothing to export — add cards first.", severity="warning")
            return
        text = deck_to_text(self.collection)
        safe_name = self.collection.name.replace("/", "_").replace("\\", "_")
        export_path = self._backend_for().file_path / f"{safe_name}.txt"
        try:
            export_path.write_text(text, encoding="utf-8")
            self.notify(f"Exported to {export_path.name}")
        except OSError as exc:
            self.notify(f"Export failed: {exc}", severity="error")

    def action_show_rulings(self) -> None:
        row = self._current_collection_list_row()
        if row is None:
            self.notify("Select a card first.", severity="warning")
            return
        self.push_screen(RulingsModal(row.entry.card))

    def action_compare_decks(self) -> None:
        self.push_screen(DeckDiffModal(self.collection, self._registry_root))

    def action_toggle_legality(self) -> None:
        panel = self.query_one("#legality-panel", Vertical)
        panel.display = not panel.display
        if panel.display:
            self._update_legality()

    # --- Callbacks ---

    def _on_new_collection_created(self, created: Deck | Binder | None) -> None:
        if created is None:
            return
        self._replace_collection(created)

    def _on_collection_loaded(self, loaded: Deck | Binder | None) -> None:
        if loaded is None:
            return
        self._replace_collection(loaded)

    def _on_deck_imported(self, deck: Deck | None) -> None:
        if deck is None:
            return
        self.collection = deck
        self._last_mana_warnings = frozenset()
        self._mark_dirty()
        self._check_mana_base()
        self._reload_collection_ui()

    def notify_collection_changed(self) -> None:
        self._mark_dirty()
        self._check_mana_base()
        self._reload_collection_ui()

    @work
    async def _reload_collection_ui(self, *, reset_highlight: bool = True) -> None:
        collection_list = self.query_one("#collection-list", ListView)
        detail = self.query_one("#entry-detail", Static)
        pane_title = self.query_one("#collection-pane-title", Static)
        pane_title.update(self._collection_kind_label())

        entries_to_show = (
            self.collection.search(name=self._filter_text)
            if self._filter_text
            else self.collection.entries
        )

        previous_index = collection_list.index
        await collection_list.query("ListItem").remove()

        if not entries_to_show:
            collection_list.index = None
            detail.update(
                "[dim]No cards match the filter.[/dim]"
                if self._filter_text
                else self._empty_detail_text()
            )
            self._update_subtitle()
            self._update_analytics()
            return

        await collection_list.extend(DeckListItem(e) for e in entries_to_show)
        n = len(entries_to_show)
        collection_list.index = 0 if (reset_highlight or previous_index is None) else min(previous_index, n - 1)

        highlighted = collection_list.highlighted_child
        detail.update(
            format_deck_entry(highlighted.entry)
            if isinstance(highlighted, DeckListItem)
            else self._empty_detail_text()
        )

        self._update_subtitle()
        self._update_analytics()


__all__ = ["MTGAssistantApp"]
