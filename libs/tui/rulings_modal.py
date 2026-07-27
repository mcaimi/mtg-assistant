#!/usr/bin/env python

"""Display official rulings for a Magic: The Gathering card."""

import asyncio
import sys
from functools import partial

try:
    from pyscryfall import ScryfallApiError, ScryfallCard, get_card_rulings
    from textual import on, work
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.screen import ModalScreen
    from textual.widgets import Button, Label, Static
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)


class RulingsModal(ModalScreen[None]):
    """Fetch and display official rulings for the given card from Scryfall."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=True),
    ]

    def __init__(self, card: ScryfallCard) -> None:
        super().__init__()
        self._card = card

    def compose(self) -> ComposeResult:
        name = self._card.name or "Unknown card"
        with Vertical(id="rulings-dialog"):
            yield Label(f"Rulings — {name}", classes="dialog-title")
            yield Static("", id="rulings-status")
            with VerticalScroll(id="rulings-scroll"):
                yield Static("", id="rulings-content")
            with Horizontal(id="rulings-buttons"):
                yield Button("Close", id="rulings-close", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#rulings-status", Static).update("[dim]Fetching rulings…[/dim]")
        self._load_rulings()

    @work
    async def _load_rulings(self) -> None:
        card_id = self._card.id
        if not card_id:
            self.query_one("#rulings-status", Static).update(
                "[yellow]Card has no Scryfall ID — cannot fetch rulings.[/yellow]"
            )
            return

        loop = asyncio.get_running_loop()
        try:
            ruling_list = await loop.run_in_executor(
                None, partial(get_card_rulings, card_id)
            )
        except ScryfallApiError as exc:
            self.query_one("#rulings-status", Static).update(f"[red]Failed: {exc}[/red]")
            return
        except Exception as exc:
            self.query_one("#rulings-status", Static).update(f"[red]Unexpected error: {exc}[/red]")
            return

        rulings = ruling_list.data
        status = self.query_one("#rulings-status", Static)
        content = self.query_one("#rulings-content", Static)

        if not rulings:
            status.update("[dim]No rulings found for this card.[/dim]")
            content.update("")
            return

        status.update(f"[dim]{len(rulings)} ruling(s)[/dim]")
        lines: list[str] = []
        for i, ruling in enumerate(rulings):
            if i > 0:
                lines.append("")
            lines.append(f"[dim]{ruling.published_at}[/dim]  [{ruling.source}]")
            lines.append(ruling.comment)
        content.update("\n".join(lines))

    @on(Button.Pressed, "#rulings-close")
    def close_pressed(self) -> None:
        self.dismiss()

    def action_close(self) -> None:
        self.dismiss()


__all__ = ["RulingsModal"]
