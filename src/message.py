import csv
from random import shuffle
from typing import List
import pandas as pd

from src.enums import Condition, CodedValues


class Messages:
    def __init__(self, path):
        """
        Read messages and associated metadata.

        :param path: File containing messages
        """
        self._messages = pd.read_csv(path)

    def __getitem__(self, key):
        return self._messages.loc[key].Message

    def __len__(self):
        return len(self._messages)

    def filter_by_condition(self, condition: Condition, values: List[CodedValues], num_messages):
        if condition is Condition.VALUES and values:
            value_names = [v.name for v in values]
            indices = self._messages.Value1.isin(value_names)
        else:
            indices = self._messages.ConditionNo == condition.value

        sample_size = min(len(self._messages[indices]), num_messages)

        self._messages = self._messages[indices].sample(sample_size, ignore_index=True)

        if self._messages.empty:
            raise Exception('No messages generated.')

        # duplicate the list and append until it's long enough
        while len(self._messages) < num_messages:
            diff = num_messages - len(self._messages)
            self._messages.append(self._messages[:diff], ignore_index=True)

    def write_to_file(self, filename, columns, header=True):
        self._messages.to_csv(filename, columns=columns, index=False, header=header)

    def add_column(self, column_name, column_data):
        self._messages[column_name] = column_data
