#!/usr/bin/env python

# Create a new deck or binder.

import sys
from pathlib import Path

try:
    from pymtgdeck import Binder, Deck
    from textual import on
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.screen import ModalScreen
    from textual.widgets import Button, Input, Label, RadioSet, Static
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

# Presets: (max_card_count, max_card_copy_count)
_PRESETS: dict[str, tuple[int, int]] = {
    "Standard": (60, 4),
    "Limited": (40, 4),
    "Commander": (100, 1),
}

class CreateModal(ModalScreen[Deck | Binder | None]):
    """Create an empty deck (with optional format preset) or a binder."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=True),
    ]

    CSS = """
    CreateModal {
        align: center middle;
    }
    #new-collection-dialog {
        width: 76;
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
    #new-collection-kind-hint {
        color: $text-muted;
        margin-bottom: 1;
    }
    #new-collection-status {
        margin: 1 0;
        min-height: 1;
    }
    #new-collection-buttons {
        height: auto;
        margin-top: 1;
    }
    """

    def __init__(self, collection_directory: Path | str) -> None:
        super().__init__()
        self._collection_dir = Path(collection_directory)

    def compose(self) -> ComposeResult:
        with Vertical(id="new-collection-dialog"):
            yield Label("New deck or binder", classes="dialog-title")
            yield Static(
                "Choose a preset or [bold]Custom Deck[/bold] to set limits manually. "
                "[bold]Binder[/bold] has no card limits.",
                id="new-collection-kind-hint",
            )
            with Horizontal(classes="field-row"):
                yield Label("Kind / Preset")
                yield RadioSet(
                    "Standard", "Limited", "Commander", "Custom Deck", "Binder",
                    id="new-collection-kind",
                )
            with Horizontal(classes="field-row"):
                yield Label("Name")
                yield Input(placeholder="Collection name", id="new-collection-name")
            with Vertical(id="new-collection-limits"):
                with Horizontal(classes="field-row"):
                    yield Label("Max cards in deck")
                    yield Input(
                        value="60",
                        id="new-collection-max-cards",
                        placeholder="60",
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Max copies per card")
                    yield Input(
                        value="4",
                        id="new-collection-max-copies",
                        placeholder="4",
                    )
            yield Static("", id="new-collection-status")
            with Horizontal(id="new-collection-buttons"):
                yield Button("Create", id="new-collection-confirm", variant="primary")
                yield Button("Cancel", id="new-collection-cancel", variant="warning")

    def on_mount(self) -> None:
        self.query_one("#new-collection-name", Input).focus()
        self._sync_limit_fields()

    def _selected_kind(self) -> str:
        rs = self.query_one("#new-collection-kind", RadioSet)
        pressed = rs.pressed_button
        return str(pressed.label) if pressed else "Standard"

    def _sync_limit_fields(self) -> None:
        kind = self._selected_kind()
        is_binder = kind == "Binder"
        is_preset = kind in _PRESETS
        max_cards_inp = self.query_one("#new-collection-max-cards", Input)
        max_copies_inp = self.query_one("#new-collection-max-copies", Input)
        max_cards_inp.disabled = is_binder or is_preset
        max_copies_inp.disabled = is_binder or is_preset
        if is_preset:
            mc, mcc = _PRESETS[kind]
            max_cards_inp.value = str(mc)
            max_copies_inp.value = str(mcc)

    @on(RadioSet.Changed, "#new-collection-kind")
    def collection_kind_changed(self, _event: RadioSet.Changed) -> None:
        self._sync_limit_fields()
        self.query_one("#new-collection-status", Static).update("")

    @staticmethod
    def _parse_positive_int(raw: str, field: str) -> int:
        text = raw.strip()
        if not text:
            raise ValueError(f"{field} is required")
        value = int(text)
        if value < 1:
            raise ValueError(f"{field} must be at least 1")
        return value

    @on(Button.Pressed, "#new-collection-confirm")
    def confirm_pressed(self) -> None:
        status = self.query_one("#new-collection-status", Static)
        name = self.query_one("#new-collection-name", Input).value.strip()
        if not name:
            status.update("[red]Please enter a name.[/red]")
            return

        kind = self._selected_kind()

        if kind == "Binder":
            self.app.notify(f"Created binder [bold]{name}[/bold]")
            self.dismiss(Binder(name=name))
            return

        if kind in _PRESETS:
            mc, mcc = _PRESETS[kind]
            deck = Deck(max_card_copy_count=mcc, max_card_count=mc, name=name)
            self.app.notify(f"Created {kind} deck [bold]{name}[/bold]")
            self.dismiss(deck)
            return

        # Custom Deck
        try:
            max_cards = self._parse_positive_int(
                self.query_one("#new-collection-max-cards", Input).value,
                "Max cards in deck",
            )
            max_copies = self._parse_positive_int(
                self.query_one("#new-collection-max-copies", Input).value,
                "Max copies per card",
            )
        except ValueError as exc:
            status.update(f"[red]{exc}[/red]")
            return

        deck = Deck(max_card_copy_count=max_copies, max_card_count=max_cards, name=name)
        self.app.notify(f"Created deck [bold]{name}[/bold]")
        self.dismiss(deck)

    @on(Button.Pressed, "#new-collection-cancel")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)

__all__ = ["CreateModal"]
