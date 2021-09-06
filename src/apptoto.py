import logging
from datetime import datetime
import time
from typing import List, Tuple

import jsonpickle
import requests
from requests.auth import HTTPBasicAuth

from src.apptoto_event import ApptotoEvent
from src.constants import MAX_EVENTS, ASH_CALENDAR_ID
from src.progress_log import print_progress
from src.participant import Participant


class ApptotoError(Exception):
    def __init__(self, message):
        """
        An exception for interactions with apptoto.

        :param message: A string describing the error
        """
        self.message = message


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
        self._timeout = 120

        # seconds between requests for apptoto burst rate limit, 100 requests per minute
        self._request_limit = 0.6
        self._last_request_time = time.time()

    def post_events(self, events: List[ApptotoEvent]):
        """
        Post events to the /v1/events API to create events that will send messages to all participants.

        :param events: List of events to create
        """
        url = f'{self._endpoint}/events'

        # Post N events at a time because Apptoto's API can't handle all events at once.
        # Too many events results in "bad gateway" error
        N = 25
        for i in range(0, len(events), N):
            events_slice = events[i:i + N]
            request_data = jsonpickle.encode({'events': events_slice, 'prevent_calendar_creation': True}, unpicklable=False)
            print_progress('Posting events {} through {} of {} to apptoto'.format(i+1, i + len(events_slice),
                                                                                  len(events)))

            while (time.time() - self._last_request_time) < self._request_limit:
                time.sleep(0.1)    
            
            r = requests.post(url=url,
                              data=request_data,
                              headers=self._headers,
                              timeout=self._timeout,
                              auth=HTTPBasicAuth(username=self._user, password=self._api_token))

            self._last_request_time = time.time()

            if r.status_code != requests.codes.ok:
               # print_progress('Failed to post events {} through {}, starting at {}'.format(i+1, len(events_slice),
               #                                                                             events[i].start_time))

                print_progress(f'Failed to post events - {str(r.status_code)} - {str(r.content)}')
                raise ApptotoError('Failed to post events: {}'.format(r.status_code))


       

    def get_events(self, begin: datetime, participant:Participant) -> List[int]:
        url = f'{self._endpoint}/events'

        event_ids = []
        page = 0

        while True:
            page += 1
            params = {'begin': begin.isoformat(),
                      'phone_number': participant.phone_number,
                      'page_size': MAX_EVENTS,
                      'page': page}

            while (time.time() - self._last_request_time) < self._request_limit:
                time.sleep(0.1)    

            r = requests.get(url=url,
                             params=params,
                             headers=self._headers,
                             timeout=self._timeout,
                             auth=HTTPBasicAuth(username=self._user, password=self._api_token))

            self._last_request_time = time.time()

            
            if r.status_code == requests.codes.ok:
                events = r.json()['events']

            else:
                print_progress(f'Failed to get events - {str(r.status_code)} - {str(r.content)}')
                raise ApptotoError('Failed to get events: {}'.format(r.status_code))

            if events:
                messages = [e['id'] for e in events if not e.get('is_deleted') 
                    and e.get('calendar_id') == ASH_CALENDAR_ID]
                event_ids.extend(messages)
                print_progress('Found {} messages from {} events for {}'.format(len(messages), 
                    len(events), participant.participant_id))

            else:
                break

        return event_ids

    def delete_event(self, event_id: int):
        url = f'{self._endpoint}/events'
        params = {'id': event_id}

        while (time.time() - self._last_request_time) < self._request_limit:
            time.sleep(0.1)    

        
        r = requests.delete(url=url,
                            params=params,
                            headers=self._headers,
                            timeout=self._timeout,
                            auth=HTTPBasicAuth(username=self._user, password=self._api_token))

        self._last_request_time = time.time()

        if not r.status_code == requests.codes.ok:
            raise ApptotoError('Failed to delete event {}: error {}'.format(event_id, r.status_code))

    def get_conversations(self, phone_number: str) -> List[Tuple[str, str]]:
        """Get timestamp and content of participant's responses."""
        url = f'{self._endpoint}/events'
        begin = datetime(year=2021, month=4, day=1).isoformat()
        params = {'begin': begin,
                  'phone_number': phone_number,
                  'include_conversations': True}

        while (time.time() - self._last_request_time) < self._request_limit:
            time.sleep(0.1)    

        r = requests.get(url=url,
                         params=params,
                         headers=self._headers,
                         timeout=self._timeout,
                         auth=HTTPBasicAuth(username=self._user, password=self._api_token))

        self._last_request_time = time.time()

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
            print_progress(f'Failed to get events - {str(r.status_code)} - {str(r.content)}')
            raise ApptotoError('Failed to get conversations: {}'.format(r.status_code))

        return conversations
