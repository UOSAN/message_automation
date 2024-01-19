from datetime import datetime
import time
from typing import List
import logging.config
import zoneinfo
import jsonpickle
import requests
from requests.auth import HTTPBasicAuth

from src.mylogging import DEFAULT_LOGGING
from src.constants import TZ_CODES


logging.config.dictConfig(DEFAULT_LOGGING)
logger = logging.getLogger(__name__)


class ApptotoParticipant:
    def __init__(self, name=None, phone=None, email=None, apptoto_id=None, external_id=None):
        """
        Create an ApptotoParticipant.

        An ApptotoParticipant represents a single participant on an ApptotoEvent.
        This participant will receive messages via email or phone.
        :param str name: Participant name (initials)
        :param str phone: Participant phone number
        :param str email: Participant email
        :param int contact_id: Participant apptoto id
        :param str contact_externalId: Participant external id
        """
        self.name = name
        self.phone = phone
        self.email = email
        self.contact_id = apptoto_id
        self.contact_external_id = external_id


class ApptotoEvent:
    def __init__(self, calendar: str, title: str, start_time: datetime,
                 content: str, participants: List[ApptotoParticipant],
                 end_time: datetime = None, external_id=None, time_zone='PT'):
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
        tzinfo = zoneinfo.ZoneInfo(TZ_CODES[time_zone])
        self.start_time = (start_time.replace(tzinfo=tzinfo)).isoformat()
        if not end_time:
            self.end_time = self.start_time
        else:
            self.end_time = (end_time.replace(tzinfo=tzinfo)).isoformat()
        self.content = content
        self.participants = participants
        self.external_id = external_id


class ApptotoError(Exception):
    def __init__(self, message):
        """
        An exception for interactions with apptoto.

        :param message: A string describing the error
        """
        self.message = message


class Apptoto:
    MAX_EVENTS = 200  # Max number of events to retrieve at one time
    MAX_POST = 20 # Max number of events to post at one time
    TIMEOUT = 240
    # seconds between requests for apptoto burst rate limit, 100 requests per minute
    # minimum = 0.6
    REQUEST_LIMIT = 0.6
    ENDPOINT = 'https://api.apptoto.com/v1'
    HEADERS = {'Content-Type': 'application/json'}

    def __init__(self, api_token: str, user: str):
        """
        Create an Apptoto instance.

        :param api_token: Apptoto API token
        :param user: Apptoto user name
        """
        self._api_token = api_token
        self._user = user
        self._last_request_time = time.time()

    def post_events(self, events: list):
        """
        Post events to the /v1/events API to create events that will send messages to all participants.

        :param events: List of events to create
        """
        url = f'{self.ENDPOINT}/events'

        # Post num_events events at a time because Apptoto's API can't handle all events at once.
        # Too many events results in "bad gateway" error
        num_events = self.MAX_POST
        posted_events = []
        for i in range(0, len(events), num_events):
            events_slice = events[i:i + num_events]
            request_data = jsonpickle.encode({'events': events_slice, 'prevent_calendar_creation': True},
                                             unpicklable=False)
            logger.info('Posting events {} through {} of {} to apptoto'.format(i + 1, i + len(events_slice),
                                                                               len(events)))

            while (time.time() - self._last_request_time) < self.REQUEST_LIMIT:
                time.sleep(0.1)

            r = requests.post(url=url,
                              data=request_data,
                              headers=self.HEADERS,
                              timeout=self.TIMEOUT,
                              auth=HTTPBasicAuth(username=self._user, password=self._api_token))

            self._last_request_time = time.time()

            if r.status_code != requests.codes.ok:
                # logger.info('Failed to post events {} through {}, starting at {}'.format(i+1, len(events_slice),
                #                                                                             events[i].start_time))

                logger.error(f'Failed to post events - {str(r.status_code)} - {str(r.content)}')
                raise ApptotoError('Failed to post events: {}'.format(r.status_code))

            posted_events.extend(r.json()['events'])

        return posted_events

    def delete_event(self, event_id: int):
        url = f'{self.ENDPOINT}/events'
        params = {'id': event_id}

        while (time.time() - self._last_request_time) < self.REQUEST_LIMIT:
            time.sleep(0.1)

        r = requests.delete(url=url,
                            params=params,
                            headers=self.HEADERS,
                            timeout=self.TIMEOUT,
                            auth=HTTPBasicAuth(username=self._user, password=self._api_token))

        self._last_request_time = time.time()

        if not r.status_code == requests.codes.ok:
            raise ApptotoError('Failed to delete event {}: error {}'.format(event_id, r.status_code))

    def get_event(self, event_id, include_conversations=False):
        url = f'{self.ENDPOINT}/event'

        params = {'id': event_id, 'include_conversations': include_conversations}

        while (time.time() - self._last_request_time) < self.REQUEST_LIMIT:
            time.sleep(0.1)
        r = requests.get(url=url,
                         params=params,
                         headers=self.HEADERS,
                         timeout=self.TIMEOUT,
                         auth=HTTPBasicAuth(username=self._user, password=self._api_token))

        self._last_request_time = time.time()
        if r.status_code == requests.codes.ok:
            return r.json()

    # TODO
    # this is just for while I'm working on things -- change max to a big number when not testing
    # otherwise sometimes I mess up and retrieve EVERYTHING from all users and it's a pain
    def get_events(self, max_to_retrieve=9999, **kwargs):
        url = f'{self.ENDPOINT}/events'

        events = []
        page = 0

        kwargs['page_size'] = self.MAX_EVENTS

        while True:
            page += 1
            kwargs['page'] = page

            r = None
            attempts = 0

            while not r and attempts < 5:
                while (time.time() - self._last_request_time) < self.REQUEST_LIMIT:
                    time.sleep(0.1)

                r = requests.get(url=url,
                                 params=kwargs,
                                 headers=self.HEADERS,
                                 timeout=self.TIMEOUT,
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

            if len(events) > max_to_retrieve:
                break

        return events

    # ex: get_contact(external_id='TAG999')
    def get_contact(self, **kwargs):
        url = f'{self.ENDPOINT}/contact'

        r = requests.get(url=url,
                         params=kwargs,
                         headers=self.HEADERS,
                         timeout=self.TIMEOUT,
                         auth=HTTPBasicAuth(username=self._user, password=self._api_token))

        if r.status_code == requests.codes.ok:
            return r.json()
        else:
            raise ApptotoError('Failed to get contact: {}'.format(r.status_code))

    def post_contact(self, contact):
        """
        Create contact in /v1/contacts API
        :param contact: contact to create
        :contact must include name, address_book
        :see apptoto api docs for full info
        """
        url = f'{self.ENDPOINT}/contacts'

        request_data = jsonpickle.encode({'contacts': [contact]}, unpicklable=False)
        logger.info(f"Posting contact {contact['name']} to apptoto")

        while (time.time() - self._last_request_time) < self.REQUEST_LIMIT:
            time.sleep(0.1)

        r = requests.post(url=url,
                          data=request_data,
                          headers=self.HEADERS,
                          timeout=self.TIMEOUT,
                          auth=HTTPBasicAuth(username=self._user, password=self._api_token))

        self._last_request_time = time.time()

        if r.status_code != requests.codes.ok:
            logger.error(f'Failed to post contact - {str(r.status_code)} - {str(r.content)}')
            raise ApptotoError('Failed to post contact: {}'.format(r.status_code))

    def put_contact(self, contact):
        """
        Update or create contact in /v1/contacts API
        :param contact: contact to update
        must include id or external_id to update existing contact
        see apptoto api docs for full info
        """
        url = f'{self.ENDPOINT}/contacts'

        request_data = jsonpickle.encode({'contacts': [contact]}, unpicklable=False)
        logger.info('Updating contact {} in apptoto'.format(contact['name']))

        while (time.time() - self._last_request_time) < self.REQUEST_LIMIT:
            time.sleep(0.1)

        r = requests.put(url=url,
                         data=request_data,
                         headers=self.HEADERS,
                         timeout=self.TIMEOUT,
                         auth=HTTPBasicAuth(username=self._user, password=self._api_token))

        self._last_request_time = time.time()

        if r.status_code != requests.codes.ok:
            logger.error(f'Failed to post contact - {str(r.status_code)} - {str(r.content)}')
            raise ApptotoError('Failed to post contact: {}'.format(r.status_code))

    def get_events_by_contact(self, begin: datetime, external_id: str, include_email=False,
                              calendar_id=None, include_conversations=False):
        contact = self.get_contact(external_id=external_id)
        phone_numbers = [p.get('normalized') for p in contact.get('phone_numbers')]
        email_addresses = [e.get('address') for e in contact.get('email_addresses')]
        events = []

        for phone in phone_numbers:
            events.extend(self.get_events(begin=begin.isoformat(), phone_number=phone,
                                          include_conversations=include_conversations))
        if include_email:
            for email in email_addresses:
                events.extend(self.get_events(begin=begin.isoformat(), email_address=email,
                                              include_conversations=include_conversations))

        if calendar_id:
            events = [e for e in events if e.get('calendar_id') == calendar_id]

        return events

    def put_events(self, events: list):
        """
        Put events to the /v1/events API to update events

        :param events: List of events to update
        """
        url = f'{self.ENDPOINT}/events'

        # Post num_events events at a time because Apptoto's API can't handle all events at once.
        # Too many events results in "bad gateway" error
        num_events = self.MAX_POST
        for i in range(0, len(events), num_events):
            events_slice = events[i:i + num_events]
            request_data = jsonpickle.encode({'events': events_slice, 'prevent_calendar_creation': True},
                                             unpicklable=False)
            logger.info('Posting events {} through {} of {} to apptoto'.format(i + 1, i + len(events_slice),
                                                                               len(events)))

            # just try again if it doesn't work
            max_attempts = 5
            remaining_attempts = max_attempts
            success = False
            while remaining_attempts and not success:
                while (time.time() - self._last_request_time) < self.REQUEST_LIMIT:
                    time.sleep(0.1)

                r = requests.put(url=url,
                                 data=request_data,
                                 headers=self.HEADERS,
                                 timeout=self.TIMEOUT,
                                 auth=HTTPBasicAuth(username=self._user, password=self._api_token))

                self._last_request_time = time.time()

                if r.status_code != requests.codes.ok:
                    remaining_attempts = remaining_attempts - 1
                    s = 's' if remaining_attempts else ''
                    logger.info(f'Failed to post, trying {remaining_attempts} more time{s}')
                else:
                    success = True

            if r.status_code != requests.codes.ok:
                # logger.info('Failed to post events {} through {}, starting at {}'.format(i+1, len(events_slice),
                #                                                                             events[i].start_time))

                logger.error(f'Failed to update events - {str(r.status_code)} - {str(r.content)}')
                raise ApptotoError('Failed to update events: {}'.format(r.status_code))
