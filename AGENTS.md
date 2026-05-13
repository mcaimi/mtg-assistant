# MTG Assistant Development Guidelines

## Project Overview
MTG Assistant is a terminal-based Magic: The Gathering deck builder using Python and the Textual framework. It manages decks and binders with Scryfall integration.

## Key Commands
- Run app: `uv run main.py`
- Install dependencies: `uv sync`

## Architecture
- **Entry point**: `main.py` resolves config and initializes `MTGAssistantApp`
- **Core app**: `libs/tui/app.py` holds main application logic
- **Data models**: Uses `pymtgdeck` for `Deck`, `Binder`, `Backend`, `Registry`
- **Configuration**: Loads from `~/.config/mtg-assistant/parameters.yaml` > `config/parameters.yaml` > `/etc/mtg-assistant/parameters.yaml`

## File Structure
```
main.py                 # Entry point
config/parameters.yaml  # Default config
libs/tui/app.py         # Main app class
libs/tui/add_card_modal.py
libs/tui/load_modal.py
libs/tui/create_modal.py
assets/decks/           # Saved deck files
assets/binders/       # Saved binder files
```

## Key Behaviors
- Default config uses local `assets/decks` and `assets/binders` directories
- Scryfall API integration via `pyscryfall`
- Collections save as JSON files via `pymtgdeck` backend
- Registry-based file discovery for decks and binders
- Supports both decks (60-card limit) and binders (no limit)

## Development Notes
- Configuration resolution follows a specific priority order
- Assets directories are created automatically if missing
- Application uses Textual framework for TUI
- All data persistence uses `pymtgdeck` library components