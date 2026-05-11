#!/usr/bin/env python

# initialize the utils package

# import the parameters class
from .parameters import Parameters

# parameters file search path
params_search_path = [
    "config/parameters.yaml",
    "~/.config/mtg-assistant/parameters.yaml",
    "/etc/mtg-assistant/parameters.yaml",
]

# export the parameters class and the parameters file search path
__all__ = ["Parameters", "params_search_path"]