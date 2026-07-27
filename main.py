#!/usr/bin/env python

import os
import sys
from pathlib import Path

# main application for the MTG Assistant TUI
try:
    from libs.utils import Parameters, params_search_path
    from libs.tui import MTGAssistantApp
    from pymtgdeck import Deck
    import yaml
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

# search for the parameters file
params_file = None
for path in params_search_path:
    path = Path(path).expanduser()
    if path.exists():
        # load the parameters file
        with open(path, "r") as f:
            params_file = yaml.load(f, Loader=yaml.FullLoader)
        break
if params_file is None:
    print("Error: parameters file not found")
    sys.exit(1)

# define a parameters file for the application
params = Parameters(params_file)

# asset directories sanity check
# if directories do not exist, create them. ignore if they already exist.(exist_ok=True)
os.makedirs(params.config.assets_base_path.decks, exist_ok=True)
os.makedirs(params.config.assets_base_path.binders, exist_ok=True)

# initialize the application
def main():
    collection = Deck.standard()
    assets = params.config.assets_base_path
    app = MTGAssistantApp(
        collection=collection,
        decks_directory=str(assets.decks),
        binders_directory=str(assets.binders),
        registry_root=str(Path(assets.decks).parent),
    )
    app.run()

if __name__ == "__main__":
    main()
