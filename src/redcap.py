from typing import Dict

import requests

from src.enums import Condition, CodedValues
from src.participant import Participant

import json


class RedcapError(Exception):
    def __init__(self, message):
        """
        An exception for interactions with REDCap.

        :param message: A string describing the error
        """
        self.message = message


class Redcap:
    def __init__(self, api_token: str, endpoint: str = 'https://redcap.uoregon.edu/api/'):
        """
        Interact with the REDCap API to collect participant information.

        :param api_token: API token for the REDCap project
        :param endpoint: REDCap endpoint URI
        """
        self._endpoint = endpoint
        self._headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        self._timeout = 15
        self._data = {'token': api_token}

    def get_participant(self, participant_id: str):
        """
        return  participant object from redcap data
        """
        session = self._get_session0()
        record = self._get_record(session, participant_id)
        if not record:
            raise RedcapError('Session 0 for subject {} not found'.format(participant_id))

        message_values = []
        task_values = []
        message_values.append(CodedValues(int(record['value1_s0'])))
        message_values.append(CodedValues(int(record['value2_s0'])))

        task_values.append(CodedValues(int(record['value1_s0'])))
        task_values.append(CodedValues(int(record['value7_s0'])))

        part = Participant()
        part.participant_id = participant_id
        part.initials = record['initials']
        part.phone_number = record['phone']
        part.session0_date = record['date_s0']
        part.quit_date = record['quitdate']
        part.wake_time = record['waketime']
        part.sleep_time = record['sleeptime']
        part.message_values = message_values
        part.task_values = task_values

        session = self._get_session1()
        record = self._get_record(session, participant_id)
        if record:
            part.condition = record['condition']

        return part

    def _get_record(self, json, participant_id: str):
        """
        get one redcap record for a specific participant
        """
        try:
            record = next(d for d in json if d['ash_id'] == participant_id)
        except StopIteration:
            record = None

        return record


    def _make_request(self, request_data: Dict[str, str], fields_for_error: str):
        request_data.update(self._data)
        r = requests.post(url=self._endpoint, data=request_data, headers=self._headers, timeout=self._timeout)
        if r.status_code == requests.codes.ok:
            return r.json()
        else:
            raise RedcapError(f'Unable to get {fields_for_error} from Redcap - {str(r.status_code)}')

    def _get_session0(self):
        request_data = {'content': 'record',
                        'format': 'json',
                        'fields[0]': 'ash_id',
                        'fields[1]': 'phone',
                        'fields[2]': 'value1_s0',
                        'fields[3]': 'value2_s0',
                        'fields[4]': 'value7_s0',
                        'fields[5]': 'initials',
                        'fields[6]': 'quitdate',
                        'fields[7]': 'date_s0',
                        'fields[8]': 'waketime',
                        'fields[9]': 'sleeptime',
                        'events[0]': 'session_0_arm_1'}
        return self._make_request(request_data, 'Session 0 data')

    def _get_session1(self):
        request_data = {'content': 'record',
                        'format': 'json',
                        'fields[0]': 'ash_id',
                        'fields[1]': 'condition',
                        'events[0]': 'session_1_arm_1'}
        return self._make_request(request_data, 'Session 1 data')



