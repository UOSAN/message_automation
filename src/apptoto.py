import logging
from datetime import datetime
from typing import List, Tuple

import jsonpickle
import requests
from requests.auth import HTTPBasicAuth

from src.apptoto_event import ApptotoEvent
from src.constants import MAX_EVENTS, ASH_CALENDAR_ID
from src.redcap import logSomething

class Apptoto:
    def __init__(self, api_token: str, user: str):
        """
        Create an Apptoto instance.

        :param api_token: Apptoto API token
        :param user: Apptoto user name
        """
        self._endpoint = 'https://api.apptoto.com/v1'
        self._api_token = api_token
        self._user = user
        self._headers = {'Content-Type': 'application/json'}
        self._timeout = 30
        self._burstlimit = 100 # apptoto burst rate limit, requests per minute

    def post_events(self, events: List[ApptotoEvent]):
        """
        Post events to the /v1/events API to create events that will send messages to all participants.

        :param events: List of events to create
        """
        url = f'{self._endpoint}/events'

        # Post 5 events at a time because Apptoto's API can't handle all events at once.
        for i in range(0, len(events), 5):
            events_slice = events[i:i + 5]
            request_data = jsonpickle.encode({'events': events_slice, 'prevent_calendar_creation': True}, unpicklable=False)
            print('Posting events to apptoto')
            r = requests.post(url=url,
                              data=request_data,
                              headers=self._headers,
                              timeout=self._timeout,
                              auth=HTTPBasicAuth(username=self._user, password=self._api_token))

            if r.status_code == requests.codes.ok:
                print('Posted events to apptoto')
            else:
                print(f'Failed to post events {i} through {i+5}, starting at {events[i].start_time}')
                print(f'Failed to post events - {str(r.status_code)} - {str(r.content)}')
                return r.status_code == requests.codes.ok

        return True

    def get_events(self, begin: datetime, phone_number: str) -> List[int]:
        url = f'{self._endpoint}/events'
        params = {'begin': begin.isoformat(),
                  'phone_number': phone_number,
                  'page_size': MAX_EVENTS}
        r = requests.get(url=url,
                         params=params,
                         headers=self._headers,
                         timeout=self._timeout,
                         auth=HTTPBasicAuth(username=self._user, password=self._api_token))

        event_ids = []
        if r.status_code == requests.codes.ok:
            events = r.json()['events']
            event_ids = [e['id'] for e in events if e.get('calendar_id') == ASH_CALENDAR_ID]
            logSomething('got {} events for {}'.format(len(event_ids), phone_number))

        else:
            print(f'Failed to get events - {str(r.status_code)} - {str(r.content)}')
            logSomething(f'Failed to get events - {str(r.status_code)} - {str(r.content)}')


        return event_ids

    def delete_event(self, event_id: int):
        url = f'{self._endpoint}/events'
        params = {'id': event_id}
        r = requests.delete(url=url,
                            params=params,
                            headers=self._headers,
                            timeout=self._timeout,
                            auth=HTTPBasicAuth(username=self._user, password=self._api_token))

        if r.status_code == requests.codes.ok:
            print(f'Deleted event - {event_id}')
            logSomething(f'Deleted event - {event_id}')

    def get_conversations(self, phone_number: str) -> List[Tuple[str, str]]:
        """Get timestamp and content of participant's responses."""
        url = f'{self._endpoint}/events'
        begin = datetime(year=2021, month=4, day=1).isoformat()
        params = {'begin': begin,
                  'phone_number': phone_number,
                  'include_conversations': True}
        r = requests.get(url=url,
                         params=params,
                         headers=self._headers,
                         timeout=self._timeout,
                         auth=HTTPBasicAuth(username=self._user, password=self._api_token))

        conversations = []
        if r.status_code == requests.codes.ok:
            response = r.json()['events']
            for e in response:
                # Check only events on the right calendar, where there is a conversation
                if e['calendar_id'] == ASH_CALENDAR_ID and \
                    e['participants'] and \
                        e['participants'][0]['conversations']:
                    for conversation in e['participants'][0]['conversations']:
                        if conversation['messages']:
                            for m in conversation['messages']:
                                # for each replied event get the content and the time.
                                # Content should be the participant's response.
                                if 'replied' in m['event_type']:
                                    conversations.append((m['at'], m['content']))
        else:
            print(f'Failed to get events - {str(r.status_code)} - {str(r.content)}')

        return conversations
