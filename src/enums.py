from enum import Enum


class Condition(Enum):
    DOWNREG = 1
    HIGHLEVEL = 2
    VALUES = 3


class CodedValues(Enum):
    humor = 1
    relationships = 2
    creativity = 3
    achievement = 4
    religious = 5
    physical = 6
    athletic = 7
    none = 8

