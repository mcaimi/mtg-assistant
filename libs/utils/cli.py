import argparse


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Magic The Gathering Assistant")
    subparsers = parser.add_subparsers(dest="command", required=True)

    load_parser = subparsers.add_parser(
        "load",
        help="Load a deck or binder from the assets directory",
    )
    load_parser.add_argument(
        "name",
        metavar="NAME",
        help="Deck or binder name (filename without .json)",
    )

    subparsers.add_parser("list", help="List all decks and binders")
    subparsers.add_parser("exit", help="Exit without starting the TUI")

    return parser
