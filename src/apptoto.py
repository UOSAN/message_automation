from datetime import datetime
import time
from typing import List
import logging.config

import jsonpickle
import requests
from requests.auth import HTTPBasicAuth

from src.constants import MAX_EVENTS
from src.mylogging import DEFAULT_LOGGING

logging.config.dictConfig(DEFAULT_LOGGING)
logger = logging.getLogger(__name__)


class ApptotoParticipant:
    def __init__(self, name: str, phone: str, email: str = ''):
        """
        Create an ApptotoParticipant.

        An ApptotoParticipant represents a single participant on an ApptotoEvent.
        This participant will receive messages via email or phone.

        :param str name: Participant name
        :param str phone: Participant phone number
        :param str email: Participant email
        """
        self.name = name
        self.phone = phone
        self.email = email

    def __str__(self):
        return '{} {} {}'.format(self.name, self.phone, self.email)


class ApptotoEvent:
    def __init__(self, calendar: str, title: str, start_time: datetime,
                 content: str, participants: List[ApptotoParticipant],
                 end_time: datetime = None):
        """
        Create an ApptotoEvent.

        An ApptotoEvent represents a single event.
        Messages will be sent at `start_time` to all `participants`.

        :param str calendar: Calendar name
        :param str title: Event title
        :param datetime start_time: Start time of event
        :param datetime end_time: End time of event (default = same as start_time)
        :param str content: Message content about event
        :param List[ApptotoParticipants] participants: Participants who will receive message content
        """
        self.calendar = calendar
        self.title = title
        self.start_time = start_time.isoformat()
        if not end_time:
            self.end_time = start_time.isoformat()
        else:
            self.end_time = end_time.isoformat()
        self.content = content

        self.participants = participants

    def __str__(self):
        return '{} {} {} {} {} {}'.format(self.calendar, self.title, self.participants, self.start_time,
                                          self.end_time, self.content)


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
        self._timeout = 240

        # seconds between requests for apptoto burst rate limit, 100 requests per minute
        self._request_limit = 0.6
        self._last_request_time = time.time()

    def post_events(self, events: List[ApptotoEvent]):
        """
        Post events to the /v1/events API to create events that will send messages to all participants.

        :param events: List of events to create
        """
        return 'done' # test modd
        url = f'{self._endpoint}/events'

        # Post num_events events at a time because Apptoto's API can't handle all events at once.
        # Too many events results in "bad gateway" error
        num_events = 25
        for i in range(0, len(events), num_events):
            events_slice = events[i:i + num_events]
            request_data = jsonpickle.encode({'events': events_slice, 'prevent_calendar_creation': True},
                                             unpicklable=False)
            logger.info('Posting events {} through {} of {} to apptoto'.format(i + 1, i + len(events_slice),
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
                # logger.info('Failed to post events {} through {}, starting at {}'.format(i+1, len(events_slice),
                #                                                                             events[i].start_time))

                logger.error(f'Failed to post events - {str(r.status_code)} - {str(r.content)}')
                raise ApptotoError('Failed to post events: {}'.format(r.status_code))

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

    def get_event(self, event_id):
        url = f'{self._endpoint}/event'

        params = {'id': event_id}

        r = requests.get(url=url,
                         params=params,
                         headers=self._headers,
                         timeout=self._timeout,
                         auth=HTTPBasicAuth(username=self._user, password=self._api_token))

        if r.status_code == requests.codes.ok:
            return r.json()

    def get_events(self, **kwargs):
        url = f'{self._endpoint}/events'

        events = []
        page = 0

        kwargs['page_size'] = MAX_EVENTS
        while True:
            page += 1
            kwargs['page'] = page

            r = None
            attempts = 0

            while not r and attempts < 5:
                while (time.time() - self._last_request_time) < self._request_limit:
                    time.sleep(0.1)

                r = requests.get(url=url,
                                 params=kwargs,
                                 headers=self._headers,
                                 timeout=self._timeout,
                                 auth=HTTPBasicAuth(username=self._user, password=self._api_token))

                self._last_request_time = time.time()
                attempts = attempts + 1

            if r.status_code == requests.codes.ok:
                new_events = r.json()['events']

            else:
                raise ApptotoError('Failed to get events: {}'.format(r.status_code))

            if new_events:
                events.extend(new_events)
                logger.info('Found {} events'.format(len(events)))
            else:
                break

        return events
