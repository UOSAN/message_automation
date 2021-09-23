from datetime import datetime
import time
from typing import List, Tuple
import logging.config

import jsonpickle
import requests
from requests.auth import HTTPBasicAuth

from src.apptoto_event import ApptotoEvent
from src.constants import MAX_EVENTS, ASH_CALENDAR_ID
from src.logging import DEFAULT_LOGGING
from src.participant import Participant

logging.config.dictConfig(DEFAULT_LOGGING)
logger = logging.getLogger(__name__)


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

                logger.info(f'Failed to post events - {str(r.status_code)} - {str(r.content)}')
                raise ApptotoError('Failed to post events: {}'.format(r.status_code))

    def _get_all_events(self, begin: datetime, participant: Participant, include_conversations=False,
                        include_deleted=False):
        url = f'{self._endpoint}/events'

        events = []
        page = 0

        while True:
            page += 1
            params = {'begin': begin.isoformat(),
                      'phone_number': participant.phone_number,
                      'include_conversations': include_conversations,
                      'page_size': MAX_EVENTS,
                      'page': page,
                      'include_deleted': include_deleted}

            while (time.time() - self._last_request_time) < self._request_limit:
                time.sleep(0.1)

            r = requests.get(url=url,
                             params=params,
                             headers=self._headers,
                             timeout=self._timeout,
                             auth=HTTPBasicAuth(username=self._user, password=self._api_token))

            self._last_request_time = time.time()

            if r.status_code == requests.codes.ok:
                new_events = r.json()['events']

            else:
                logger.info(f'Failed to get events - {str(r.status_code)} - {str(r.content)}')
                raise ApptotoError('Failed to get events: {}'.format(r.status_code))

            if new_events:
                events.extend(new_events)
                logger.info('Found {} events for {}'.format(len(events),
                                                            participant.participant_id))
            else:
                break

        return events

    def get_messages(self, begin: datetime, participant: Participant) -> List[int]:

        events = self._get_all_events(begin, participant)
        messages = [e['id'] for e in events if not e.get('is_deleted')
                    and e.get('calendar_id') == ASH_CALENDAR_ID]

        logger.info('Found {} messages from {} events for {}'.format(len(messages),
                                                                     len(events),
                                                                     participant.participant_id))

        # added for debugging
        '''
        csv_path = Path(DOWNLOAD_DIR)
        events_file = csv_path / (participant.participant_id + '_events.csv')
        with open(events_file, 'w') as ef:
            fieldnames = ['title', 'start_time', 'content']
            writer = csv.DictWriter(ef, fieldnames=fieldnames,
                                    extrasaction='ignore')
            writer.writeheader()
            for event in events:
                if event['id'] in messages:
                    writer.writerow(event)
        '''

        return messages

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

    def get_responses(self, participant) -> List[Tuple[str, str]]:
        """Get timestamp and content of participant's responses."""

        begin = datetime(year=2021, month=4, day=1)
        events = self._get_all_events(begin, participant, include_conversations=True)

        # Check only events on the right calendar, where there is a conversation
        conversation_events = [e for e in events if e['calendar_id'] == ASH_CALENDAR_ID and
                               e['participants'] and e['participants'][0]['conversations']]

        responses = []
        for event in conversation_events:
            conversations = [c for c in event['participants'][0]['conversations'] if c['messages']]
            for conversation in conversations:
                for message in conversation['messages']:
                    # for each replied event get the content and the time.
                    # Content should be the participant's response.
                    if 'replied' in message['event_type']:
                        responses.append((message['at'], message['content']))

        return responses

    def _get_one_event(self, id):
        url = f'{self._endpoint}/event'

        params = {'id': id,
                  'include_conversations': True}

        r = requests.get(url=url,
                         params=params,
                         headers=self._headers,
                         timeout=self._timeout,
                         auth=HTTPBasicAuth(username=self._user, password=self._api_token))

        if r.status_code == requests.codes.ok:
            return r.json()

    def _get_some_events(self, **kwargs):

        url = f'{self._endpoint}/events'

        events = []
        page = 0

        kwargs['page_size'] = MAX_EVENTS
        while True:
            page += 1
            kwargs['page'] = page

            while (time.time() - self._last_request_time) < self._request_limit:
                time.sleep(0.1)

            r = requests.get(url=url,
                             params=kwargs,
                             headers=self._headers,
                             timeout=self._timeout,
                             auth=HTTPBasicAuth(username=self._user, password=self._api_token))

            self._last_request_time = time.time()

            if r.status_code == requests.codes.ok:
                new_events = r.json()['events']

            else:
                raise ApptotoError('Failed to get events: {}'.format(r.status_code))

            if new_events:
                events.extend(new_events)

            else:
                break

        return events
