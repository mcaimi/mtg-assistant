#!/usr/bin/env python

# Create a new deck or binder.

from pathlib import Path

# import the necessary modules
try:
    from pymtgdeck import Binder, Deck
    from pymtgdeck.entities.deck import MAX_CARD_COPY_COUNT, MAX_CARD_COUNT
    from textual import on
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.screen import ModalScreen
    from textual.widgets import Button, Input, Label, RadioSet, Static
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

# create modal window in textual
class CreateModal(ModalScreen[Deck | Binder | None]):
    """Create an empty deck (with size and per-card copy limits) or a binder (no such limits)."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=True),
    ]

    CSS = """
    CreateModal {
        align: center middle;
    }
    #new-collection-dialog {
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
                "Choose the kind, set a name, then confirm. Decks use the limits below; binders do not.",
                id="new-collection-kind-hint",
            )
            with Horizontal(classes="field-row"):
                yield Label("Kind")
                yield RadioSet("Deck", "Binder", id="new-collection-kind")
            with Horizontal(classes="field-row"):
                yield Label("Name")
                yield Input(placeholder="Collection name", id="new-collection-name")
            with Vertical(id="new-collection-limits"):
                with Horizontal(classes="field-row"):
                    yield Label("Max cards in deck")
                    yield Input(
                        value=str(MAX_CARD_COUNT),
                        id="new-collection-max-cards",
                        placeholder=str(MAX_CARD_COUNT),
                    )
                with Horizontal(classes="field-row"):
                    yield Label("Max copies per card")
                    yield Input(
                        value=str(MAX_CARD_COPY_COUNT),
                        id="new-collection-max-copies",
                        placeholder=str(MAX_CARD_COPY_COUNT),
                    )
            yield Static("", id="new-collection-status")
            with Horizontal(id="new-collection-buttons"):
                yield Button("Create", id="new-collection-confirm", variant="primary")
                yield Button("Cancel", id="new-collection-cancel", variant="warning")

    def on_mount(self) -> None:
        self.query_one("#new-collection-name", Input).focus()
        self._sync_limit_fields_enabled()

    def _is_binder_selected(self) -> bool:
        rs = self.query_one("#new-collection-kind", RadioSet)
        pressed = rs.pressed_button
        if pressed is None:
            return False
        return str(pressed.label) == "Binder"

    def _sync_limit_fields_enabled(self) -> None:
        binder = self._is_binder_selected()
        for input_id in ("#new-collection-max-cards", "#new-collection-max-copies"):
            self.query_one(input_id, Input).disabled = binder

    @on(RadioSet.Changed, "#new-collection-kind")
    def collection_kind_changed(self, _event: RadioSet.Changed) -> None:
        self._sync_limit_fields_enabled()
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

        if self._is_binder_selected():
            binder = Binder(name=name)
            self.app.notify(f"Created binder [bold]{name}[/bold]")
            self.dismiss(binder)
            return

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

        deck = Deck(
            max_card_copy_count=max_copies,
            max_card_count=max_cards,
            name=name,
        )
        self.app.notify(f"Created deck [bold]{name}[/bold]")
        self.dismiss(deck)

    @on(Button.Pressed, "#new-collection-cancel")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)

# export the create modal class
__all__ = ["CreateModal"]