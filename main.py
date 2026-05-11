#!/usr/bin/env python

import os
import sys

# main application for the MTG Assistant TUI
try:
    from libs.utils import Parameters
    from libs.tui import MTGAssistantApp
    from pymtgdeck import Deck
    import yaml
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

# parameters file search path
params_search_path = [
    "config/parameters.yaml",
    "~/.config/mtg-assistant/parameters.yaml",
    "/etc/mtg-assistant/parameters.yaml",
]

# search for the parameters file
params_file = None
for path in params_search_path:
    if os.path.exists(path):
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

deck = Deck()
app = MTGAssistantApp(
    deck=deck,
    decks_directory=params.config.assets_base_path.decks,
)
app.run()
