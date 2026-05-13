#!/usr/bin/env python

# Pick a saved deck or binder.

import json
from pathlib import Path


# import the necessary modules
try:
    from pymtgdeck import Binder, Deck, Registry
    from textual import on, work
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.screen import ModalScreen
    from textual.widgets import Button, Label, ListItem, ListView, Static
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

# confirm delete collection modal window in textual
class ConfirmDeleteCollectionModal(ModalScreen[bool]):
    """Ask before removing a deck or binder JSON file from disk."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    CSS = """
    ConfirmDeleteCollectionModal {
        align: center middle;
    }
    #confirm-delete-dialog {
        width: 62;
        height: auto;
        border: thick $error;
        background: $surface;
        padding: 1 2;
    }
    .dialog-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #confirm-delete-warning {
        color: $text-muted;
        margin-bottom: 1;
    }
    #confirm-delete-buttons {
        height: auto;
        margin-top: 1;
    }
    """

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-delete-dialog"):
            yield Static(
                f"Delete file [bold]{self._path.name}[/bold]?",
                classes="dialog-title",
            )
            yield Static("This cannot be undone.", id="confirm-delete-warning")
            with Horizontal(id="confirm-delete-buttons"):
                yield Button("Delete", id="confirm-delete-yes", variant="error")
                yield Button("Cancel", id="confirm-delete-no", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#confirm-delete-no", Button).focus()

    @on(Button.Pressed, "#confirm-delete-yes")
    def confirm_pressed(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#confirm-delete-no")
    def cancel_pressed(self) -> None:
        self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)


def load_collection_from_path(path: Path) -> Deck | Binder:
    """Load a ``Deck`` or ``Binder`` from a ``Backend`` envelope JSON on disk."""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError("File must contain a JSON object")
    kind = raw.get("type")
    data = raw.get("data")
    if kind == "Deck" and isinstance(data, dict):
        return Deck.from_dict(data)
    if kind == "Binder" and isinstance(data, dict):
        return Binder.from_dict(data)
    raise ValueError(f"Unsupported or missing type (expected Deck or Binder), got {kind!r}")


class CollectionFileListItem(ListItem):
    """One row in the load dialog, backed by a path from ``Registry``."""

    def __init__(self, path: Path, collection_type: str, display_name: str) -> None:
        self.path = path
        self.collection_type = collection_type
        self.load_error: str | None = None
        self.collection: Deck | Binder | None = None
        try:
            self.collection = load_collection_from_path(path)
            label_text = f"[{self.collection_type}] {display_name}"
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            label_text = f"{path.name}  [invalid: {exc}]"
            self.load_error = str(exc)
        super().__init__(Label(label_text))


class LoadModal(ModalScreen[Deck | Binder | None]):
    """Pick a saved ``Deck`` or ``Binder`` discovered via ``Registry`` under ``registry_root``."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=True),
        Binding("d", "delete_selected", "Delete file"),
    ]

    CSS = """
    LoadModal {
        align: center middle;
    }
    #load-collection-dialog {
        width: 80;
        max-height: 90%;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #collection-files-list {
        height: 16;
        margin: 1 0;
    }
    .dialog-title {
        text-style: bold;
        margin-bottom: 1;
    }
    """

    def __init__(self, registry_root: Path | str) -> None:
        super().__init__()
        self._registry_root = Path(registry_root)
        self._delete_target: Path | None = None

    def _registry_entries(self) -> list[dict]:
        reg = Registry(str(self._registry_root))
        return sorted(
            reg.registry,
            key=lambda e: (str(e.get("type", "")), str(e.get("name", "")).lower(), str(e.get("path", ""))),
        )

    def compose(self) -> ComposeResult:
        with Vertical(id="load-collection-dialog"):
            yield Static("Load deck or binder", classes="dialog-title")
            yield Static(
                "Saved collections (↑↓). [bold]Enter[/bold] loads. [bold]d[/bold] deletes "
                "(with confirmation). [bold]Escape[/bold] closes.",
                classes="help",
            )
            entries = self._registry_entries()
            if not entries:
                yield Static(
                    f"No Deck/Binder JSON under [bold]{self._registry_root}[/bold].",
                    id="no-files",
                )
            yield ListView(
                *[
                    CollectionFileListItem(
                        Path(e["path"]),
                        str(e.get("type", "?")),
                        str(e.get("name", Path(e["path"]).name)),
                    )
                    for e in entries
                ],
                id="collection-files-list",
                initial_index=0 if entries else None,
            )
            with Vertical(classes="button-row"):
                yield Button("Close", id="load-collection-close", variant="warning")

    def on_mount(self) -> None:
        lv = self.query_one("#collection-files-list", ListView)
        if lv.children:
            lv.focus()
        else:
            self.query_one("#load-collection-close", Button).focus()

    @on(ListView.Selected, "#collection-files-list")
    def collection_file_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if not isinstance(item, CollectionFileListItem):
            return
        if item.collection is None:
            self.app.notify(
                f"Cannot load {item.path.name}: {item.load_error or 'unknown error'}",
                severity="error",
            )
            return
        self.dismiss(item.collection)

    @on(Button.Pressed, "#load-collection-close")
    def close_pressed(self) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)

    def action_delete_selected(self) -> None:
        lv = self.query_one("#collection-files-list", ListView)
        item = lv.highlighted_child
        if not isinstance(item, CollectionFileListItem):
            return
        self._delete_target = item.path
        self.app.push_screen(ConfirmDeleteCollectionModal(item.path), self._after_delete_confirm)

    def _after_delete_confirm(self, confirmed: bool | None) -> None:
        path = self._delete_target
        self._delete_target = None
        if not confirmed or path is None:
            return
        try:
            path.unlink()
        except OSError as exc:
            self.app.notify(f"Could not delete file: {exc}", severity="error")
            return
        self.app.notify(f"Deleted {path.name}")
        self._refresh_collection_file_list()

    @work
    async def _refresh_collection_file_list(self) -> None:
        lv = self.query_one("#collection-files-list", ListView)
        await lv.query("ListItem").remove()
        entries = self._registry_entries()
        if entries:
            await lv.extend(
                CollectionFileListItem(
                    Path(e["path"]),
                    str(e.get("type", "?")),
                    str(e.get("name", Path(e["path"]).name)),
                )
                for e in entries
            )
            lv.index = 0
        else:
            lv.index = None

# export the load modal class
__all__ = ["LoadModal"]