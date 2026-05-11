#!/usr/bin/env python

# load configuration parameters from yaml file

# define a class to load configuration parameters from yaml file
class Parameters(object):
    def __init__(self, data: dict):
        """
        Initialize the Parameters class.
        
        Args:
            data: A dictionary of configuration parameters.
        """
        if not isinstance(data, dict):
            raise TypeError(f"Parameters: expected 'dict', got {type(data)}.")
        
        # store the data in the class
        self.data = data

        # iterate over the keys in the data
        for k in self.data.keys():
            # if the value is not a dictionary, set the attribute
            if type(self.data.get(k)) != dict:
                self.__setattr__(k, self.data.get(k))
            else:
                self.__setattr__(k, Parameters(self.data.get(k)))

# export the class
__all__ = ["Parameters"]