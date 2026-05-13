#!/usr/bin/env python

"""Plain-text / Rich markup helpers for card and deck entry display."""


# import the necessary modules
try:
    from pymtgdeck import Entry
    from pyscryfall import ScryfallCard
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

# format a Scryfall card for the detail / preview panel
def format_scryfall_card(card: ScryfallCard) -> str:
    """Format a Scryfall card for the detail / preview panel."""
    lines: list[str] = []
    name = card.name or "(unnamed)"
    lines.append(f"[bold]{name}[/bold]")
    if card.mana_cost:
        lines.append(f"Mana cost: {card.mana_cost}")
    if card.cmc is not None:
        lines.append(f"CMC: {card.cmc}")
    if card.type_line:
        lines.append(card.type_line)
    if card.set or card.collector_number:
        set_p = card.set or "?"
        cn = card.collector_number or "?"
        lines.append(f"Set: {set_p} #{cn}" + (f" — {card.set_name}" if card.set_name else ""))

    if card.oracle_text:
        lines.append("")
        lines.append(card.oracle_text)
    elif card.card_faces:
        for face in card.card_faces:
            lines.append("")
            fn = face.name or "Face"
            lines.append(f"[bold]{fn}[/bold]")
            if face.mana_cost:
                lines.append(f"  {face.mana_cost}")
            if face.type_line:
                lines.append(face.type_line)
            if face.oracle_text:
                lines.append(face.oracle_text)

    if card.rarity:
        lines.append("")
        lines.append(f"Rarity: {card.rarity}")
    return "\n".join(lines)


def format_deck_entry(entry: Entry) -> str:
    """Format a deck entry (card + quantity) for the right pane."""
    head = f"[bold]{entry.card.name or '?'}[/bold]  ×{entry.count}"
    body = format_scryfall_card(entry.card)
    return f"{head}\n\n{body}"
