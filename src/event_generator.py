import random
from collections import namedtuple
from datetime import datetime, timedelta, date, time, timezone
from pathlib import Path
from typing import List
import logging.config
import pandas as pd
import re
import json

from src.mylogging import DEFAULT_LOGGING
from src.apptoto import Apptoto, ApptotoEvent, ApptotoParticipant, ApptotoError
from src.constants import DAYS_1, DAYS_2, MESSAGES_PER_DAY_1, MESSAGES_PER_DAY_2
from src.enums import Condition, CodedValues
from src.participant import RedcapParticipant
from src.message import Messages
from src.constants import DOWNLOAD_DIR, ASH_CALENDAR_ID

logging.config.dictConfig(DEFAULT_LOGGING)
logger = logging.getLogger(__name__)

SMS_TITLE = 'ASH SMS'
CIGS_TITLE = 'ASH CIGS'
TASK_MESSAGES = 20
ITI = [
    0.0,
    1.2,
    1.9,
    1.8,
    2.2,
    1.2,
    2.8,
    1.1,
    2.1,
    2.0,
    1.7,
    1.1,
    1.3,
    5.3,
    1.0,
    1.2,
    1.5,
    3.4,
    2.1,
    1.0
]


# see stack overflow 51918580
def random_times(start: datetime, end: datetime, n: int) -> List[datetime]:
    """
    Create randomly spaced times between start and end time.
    :param n:
    :param start: Start time
    :type start: datetime
    :param end: End time
    :type end: datetime
    :param n: Number of times to create
    :return: List of datetime
    """
    # minimum minutes between times
    min_interval = 60
    delta = end - start
    range_max = int(delta.total_seconds() / 60) - ((min_interval - 1) * (n - 1))
    r = [(min_interval - 1) * i + x for i, x in enumerate(sorted(random.sample(range(range_max), n)))]
    times = [start + timedelta(minutes=x) for x in r]
    return times


def condition_abbrev(condition: Condition) -> str:
    if condition == Condition.VALUES:
        return 'Values'
    elif condition == Condition.HIGHLEVEL:
        return 'HLC'
    elif condition == Condition.DOWNREG:
        return 'CR'
    else:
        assert 'Invalid condition'


def normalize_phone(phone):
    phone = phone.lstrip('+1')
    phone = re.sub("[ ()-]", '', phone)  # remove space, (), -
    assert (len(phone) == 10)
    phone = f"+1{phone}"
    return phone


def check_fields(subject: RedcapParticipant, required_fields):
    if subject.redcap.s0[required_fields].isnull().any():
        missing = [x for x in required_fields if pd.isnull(subject.redcap.s0[x])]
        missing_text = ', '.join(missing)
        raise Exception(f'Missing required redcap data for {subject.id}: {missing_text}')


# Get dates for diary messages, always including at least one weekend day
def get_diary_dates(start_date: date, number_of_days=4):
    dates = [start_date + timedelta(days=d) for d in range(0, number_of_days)]
    day_of_week = [d.weekday() for d in dates]
    # shift by one day until you have at least one weekend day
    # 5 = Saturday, 6 = Sunday
    while max(day_of_week) < 5:
        dates = [d + timedelta(days=1) for d in dates]
        day_of_week = [d.weekday() for d in dates]
    return dates


class EventGenerator:
    def __init__(self, participant_id, config, instance_path):
        self.participant_id = participant_id
        self.config = config
        self.instance_path = Path(instance_path)
        self.apptoto = Apptoto(api_token=config['apptoto_api_token'],
                               user=config['apptoto_user'])
        self.events_file = self.instance_path / 'events.json'
        self.message_file = self.instance_path / self.config['message_file']

    def _update_events_file(self, events):
        event_ids = [e['id'] for e in events]

        if self.events_file.exists():
            with open(self.events_file, 'r') as f:
                all_events = json.load(f)
        else:
            all_events = dict()
        if all_events.get(self.participant_id):
            all_events.get(self.participant_id).extend(event_ids)
        else:
            all_events[self.participant_id] = event_ids

        with open(self.events_file, 'w') as f:
            json.dump(all_events, f)

    def _get_event_ids(self):
        if self.events_file.exists():
            with open(self.events_file, 'r') as f:
                all_events = json.load(f)
            return all_events.get(self.participant_id)
        else:
            return None

    def daily_diary_one(self):
        """
        Generate events for the first round of daily diary messages,
        which are sent after session 0, before session 1.
        :return:
        """
        subject = RedcapParticipant(self.participant_id,
                                    self.config['redcap_api_token'])

        # check that we have the required info from redcap
        check_fields(subject, ['initials', 'phone', 'sleeptime', 'email', 'date_s0'])

        participants = [ApptotoParticipant(subject.id,
                                           subject.redcap.s0.phone,
                                           subject.redcap.s0.email)]

        events = []

        # Diary round 1
        round1_start = date.fromisoformat(subject.redcap.s0.date_s0) + timedelta(days=2)
        round1_dates = get_diary_dates(round1_start)
        sleep_time = time.fromisoformat(subject.redcap.s0.sleeptime)
        for day, message_date in enumerate(round1_dates):
            content = f'UO: Daily Diary #{day + 1}'
            title = f'ASH Daily Diary #{day + 1}'
            message_datetime = datetime.combine(message_date, sleep_time) - timedelta(hours=2)
            events.append(ApptotoEvent(calendar=self.config['apptoto_calendar'],
                                       title=title,
                                       start_time=message_datetime,
                                       content=content,
                                       participants=participants))

        if len(events) > 0:
            posted_events = self.apptoto.post_events(events)
            self._update_events_file(posted_events)

        return 'Diary round 1 created'

    def daily_diary_three(self):
        """
        Generate events for the third round of daily diary messages,
        which are sent after session 2.
        :return:
        """
        subject = RedcapParticipant(self.participant_id,
                                    self.config['redcap_api_token'])
        # first check that we have the required info from redcap
        check_fields(subject, ['initials', 'phone', 'sleeptime', 'email'])

        if 's1' not in subject.redcap or pd.isnull(subject.redcap.s1.training_end):
            return f'Missing session1 training end date for {subject.id}'

        participants = [ApptotoParticipant(subject.id,
                                           subject.redcap.s0.phone,
                                           subject.redcap.s0.email)]

        events = []

        # Diary round 3
        round3_start = date.fromisoformat(subject.redcap.s1.training_end) + timedelta(weeks=6)
        round3_dates = get_diary_dates(round3_start)
        sleep_time = time.fromisoformat(subject.redcap.s0.sleeptime)
        for day, message_date in enumerate(round3_dates):
            content = f'UO: Daily Diary #{day + 9}'
            title = f'ASH Daily Diary #{day + 9}'
            message_datetime = datetime.combine(message_date, sleep_time) - timedelta(hours=2)
            events.append(ApptotoEvent(calendar=self.config['apptoto_calendar'],
                                       title=title,
                                       start_time=message_datetime,
                                       content=content,
                                       participants=participants))

        if len(events) > 0:
            posted_events = self.apptoto.post_events(events)
            self._update_events_file(posted_events)

        return 'Diary round 3 created'

    def generate_messages(self):
        """
        Generate events for intervention messages, messages about daily cigarette usage,
        messages for boosters, daily diary rounds 2, 3 and 4.
        :return:
        """
        subject = RedcapParticipant(self.participant_id,
                                    self.config['redcap_api_token'])
        # first check that we have the required info from redcap
        check_fields(subject, ['value1_s0', 'value2_s0', 'initials', 'phone',
                               'sleeptime', 'waketime', 'quitdate', 'email'])

        participants = [ApptotoParticipant(subject.id,
                                           subject.redcap.s0.phone,
                                           subject.redcap.s0.email)]

        events = []

        messages = Messages(self.message_file)
        num_required_messages = 28 * (MESSAGES_PER_DAY_1 + MESSAGES_PER_DAY_2)
        condition = Condition(int(subject.redcap.s1.condition))
        message_values = [CodedValues(int(subject.redcap.s0.value1_s0)),
                          CodedValues(int(subject.redcap.s0.value2_s0))]

        messages.filter_by_condition(condition,
                                     message_values,
                                     num_required_messages)

        quit_date = date.fromisoformat(subject.redcap.s0.quitdate)
        wake_time = time.fromisoformat(subject.redcap.s0.waketime)
        sleep_time = time.fromisoformat(subject.redcap.s0.sleeptime)

        Event = namedtuple('Event', ['time', 'title', 'content'])

        # Add quit_message_date date boosters 3 hrs after wake time
        message_datetime = datetime.combine(quit_date - timedelta(days=1), wake_time) + timedelta(hours=3)
        events.append(Event(time=message_datetime, title='UO: Day Before', content='UO: Day Before Quitting'))
        message_datetime = datetime.combine(quit_date, wake_time) + timedelta(hours=3)
        events.append(Event(time=message_datetime, title='UO: Quit Date', content='UO: Quit Date'))

        # Add one message per day asking for a reply with the number of cigarettes smoked, 1 hr before bedtime
        for days in range(DAYS_1 + DAYS_2):
            message_date = quit_date + timedelta(days=days)
            message_datetime = datetime.combine(message_date, sleep_time) - timedelta(hours=1)
            content = "UO: Good evening! Please respond with the number of cigarettes you have smoked today. " \
                      "If you have not smoked any cigarettes, please respond with a 0. Thank you!"
            events.append(Event(time=message_datetime, title=CIGS_TITLE, content=content))

        # Add booster messages, 3 hrs before bedtime
        n = 1
        booster_dates = []
        for days in range(1, 51, 7):
            message_date = quit_date + timedelta(days=days)
            booster_dates.append(message_date)
            message_datetime = datetime.combine(message_date, sleep_time) - timedelta(hours=3)

            title = f'{condition_abbrev(condition)} Booster {n}'
            content = "UO: Booster session"
            events.append(Event(time=message_datetime, title=title, content=content))
            n = n + 1

            message_date = quit_date + timedelta(days=(days + 3))
            booster_dates.append(message_date)
            message_datetime = datetime.combine(message_date, sleep_time) - timedelta(hours=3)
            title = f'{condition_abbrev(condition)} Booster {n}'
            content = "UO: Booster session"
            events.append(Event(time=message_datetime, title=title, content=content))
            n = n + 1

        # Add daily diary round 2 messages, 2 hrs before bedtime
        round2_start = quit_date + timedelta(weeks=4)
        round2_dates = get_diary_dates(round2_start)
        for day, message_date in enumerate(round2_dates):
            message_datetime = datetime.combine(message_date, sleep_time) - timedelta(hours=2)
            content = f'UO: Daily Diary #{day + 5}'
            title = f'ASH Daily Diary #{day + 5}'
            events.append(Event(time=message_datetime, title=title, content=content))

        # Generate intervention messages
        logger.info(f'Generating intervention messages for {subject.id}')
        n = 0
        for day in range(DAYS_1 + DAYS_2):
            message_date = quit_date + timedelta(days=day)
            if message_date == quit_date:
                start_time = datetime.combine(message_date, wake_time) + timedelta(hours=4)
            else:
                start_time = datetime.combine(message_date, wake_time)

            if message_date in booster_dates:
                end_time = datetime.combine(message_date, sleep_time) - timedelta(hours=4)
            elif message_date in round2_dates:
                end_time = datetime.combine(message_date, sleep_time) - timedelta(hours=3)
            else:
                end_time = datetime.combine(message_date, sleep_time) - timedelta(hours=2)

            # Get times each day to send messages
            # Send 5 messages a day for the first 28 days, 4 after
            if day in range(DAYS_1):
                n_messages = MESSAGES_PER_DAY_1
            else:
                n_messages = MESSAGES_PER_DAY_2
            times_list = random_times(start_time, end_time, n_messages)
            for t in times_list:
                # Prepend each message with "UO: "
                content = "UO: " + messages[n]
                events.append(Event(time=t, title=SMS_TITLE, content=content))
                n = n + 1

        if len(events) > 0:
            apptoto_events = []
            for e in sorted(events):
                apptoto_events.append(ApptotoEvent(calendar=self.config['apptoto_calendar'],
                                                   title=e.title,
                                                   start_time=e.time,
                                                   content=e.content,
                                                   participants=participants))

            posted_events = self.apptoto.post_events(apptoto_events)
            self._update_events_file(posted_events)

            csv_path = Path(DOWNLOAD_DIR)
            if not csv_path.exists():
                csv_path.mkdir()
            f = csv_path / (subject.id + '_messages.csv')
            messages.write_to_file(f, columns=['UO_ID', 'Message'])

        return f'Messages written to {subject.id}_messages.csv'

    def generate_task_files(self):
        subject = RedcapParticipant(self.participant_id,
                                    self.config['redcap_api_token'])
        # first check that we have the required info from redcap
        check_fields(subject, ['value1_s0', 'value7_s0'])

        csv_path = Path(DOWNLOAD_DIR)
        task_values = [CodedValues(int(subject.redcap.s0.value1_s0)),
                       CodedValues(int(subject.redcap.s0.value7_s0))]

        for session in range(1, 3):
            for run in range(1, 5):
                messages = Messages(self.message_file)
                messages.filter_by_condition(Condition.VALUES,
                                             task_values,
                                             TASK_MESSAGES)
                messages.add_column('iti', ITI)
                file_name = csv_path / f'VAFF_{subject.id}_Session{session}_Run{run}.csv'
                messages.write_to_file(file_name, columns=['Message', 'iti'],
                                       header=['message', 'iti'])
                logger.info(f'Wrote {file_name.name}')

        return f'Task files created for {subject.id}'

    def get_conversations(self):
        """Get timestamp and content of all message to and from participant."""

        begin = datetime(year=2021, month=4, day=1)
        """events = self.apptoto.get_events_by_contact(begin,
                                                    external_id=self.participant_id,
                                                    calendar_id=ASH_CALENDAR_ID,
                                                    include_conversations=True)"""

        event_ids = self._get_event_ids()
        logger.info(f'Searching {len(event_ids)} events')
        # I had getevents(eid, begin, True) here -- I'm guessing I was in the middle of changing things
        events = self.apptoto.get_events(begin=begin, include_conversations=True)

        conversations = pd.json_normalize(events, record_path=['participants',
                                                               'conversations',
                                                               'messages'],
                                          meta=['title',
                                                'start_time',
                                                'calendar_id',
                                                ['participants', 'event_id']])

        csv_path = Path(DOWNLOAD_DIR)

        conversations = conversations[conversations.calendar_id == ASH_CALENDAR_ID]
        conversations['start_time'] = pd.to_datetime(conversations['start_time'])

        messages = pd.read_csv(self.message_file, dtype=str)
        messages['content'] = 'UO: ' + messages.Message
        conversations = conversations.merge(messages, on='content', how='left').set_index('id')

        sms_convos = conversations[conversations.title.str.contains(SMS_TITLE)]

        sms_name = csv_path / f'{self.participant_id}_sms_conversations.csv'

        columns = ['at', 'event_type', 'UO_ID', 'content', 'title',
                   'delivery_state', 'delivery_error', 'delivery_failed', 'send_failed']
        sms_convos.to_csv(sms_name, date_format='%x %X', columns=columns)

        cig_convos = conversations[conversations.title.str.contains(CIGS_TITLE)]
        cig_name = csv_path / f'{self.participant_id}_cig_conversations.csv'
        cig_convos.to_csv(cig_name, date_format='%x %X', columns=columns)

        return f'Conversations written to {sms_name.name} and {cig_name.name}'

    def delete_messages(self):

        begin = datetime.now(timezone.utc)
        """
        'new' way, currently too slow
        event_ids = self._get_event_ids()
        events = []
        for e_id in event_ids:
            events.append(self.apptoto.get_event(e_id))
        future_ids = [e['id'] for e in events if datetime.fromisoformat(e['start_time']) > begin]
        """
        """
        events = apptoto.get_events(begin=begin.isoformat(),
                                    phone_number=subject.redcap.s0.phone)
        event_ids = [e['id'] for e in events if not e.get('is_deleted')
                     and e.get('calendar_id') == ASH_CALENDAR_ID]"""

        events = self.apptoto.get_events_by_contact(begin,
                                                    external_id=self.participant_id,
                                                    calendar_id=ASH_CALENDAR_ID)

        event_ids = list({e['id'] for e in events})
        logger.info(f'Found {len(event_ids)} events for {self.participant_id}')

        deleted = 0
        for event_id in event_ids:
            self.apptoto.delete_event(event_id)
            deleted += 1
            logger.info('Deleted event {}, {} of {}'.format(event_id, deleted, len(event_ids)))

        return f'Deleted {len(event_ids)} messages for {self.participant_id}'

    def update_events(self):
        # get all future events for a subject
        # Add or change phone & email to match redcap information
        subject = RedcapParticipant(self.participant_id,
                                    self.config['redcap_api_token'])
        begin = datetime.now(timezone.utc)
        event_ids = self._get_event_ids()

        """  events = []
        for e_id in event_ids:
            events.append(self.apptoto.get_event(e_id))
        events = [e for e in events if datetime.fromisoformat(e['start_time']) > begin]"""

        events = self.apptoto.get_events_by_contact(begin,
                                                    external_id=self.participant_id,
                                                    calendar_id=ASH_CALENDAR_ID)

        e_df = pd.DataFrame.from_records(events)
        e_df.drop_duplicates(subset='id', inplace=True)

        e_df.rename(columns={'calendar_name': 'calendar'}, inplace=True)
        e_df.drop(columns='is_deleted', inplace=True)

        phone = normalize_phone(subject.redcap.s0.phone)
        email = subject.redcap.s0.email

        # check email, phone against new values
        e_df['phone'] = [p[0]['normalized_phone'] for p in e_df.participants]
        e_df['email'] = [p[0]['email'] for p in e_df.participants]
        e_df = e_df[(e_df.phone != phone) | (e_df.email != email)]
        e_df.drop(columns=['phone', 'email'], inplace=True)
        new_participant = {'name': subject.id, 'phone': phone, 'email': email}
        e_df['participants'] = [[new_participant] for i in range(0, len(e_df))]
        updated_events = e_df.to_dict(orient='records')
        self.apptoto.put_events(updated_events)

        return f'Updated {len(updated_events)} events for subject {subject.id}'

    # do we need to check primary phone/email?
    def update_contact(self):

        subject = RedcapParticipant(self.participant_id,
                                    self.config['redcap_api_token'])

        phone = normalize_phone(subject.redcap.s0.phone)
        email = subject.redcap.s0.email

        contact_exists = False
        try:
            contact = self.apptoto.get_contact(external_id=subject.id)
            contact_exists = True
        except ApptotoError:
            logger.info(f'Adding {subject.id} to apptoto address book')
            contact = {'external_id': subject.id, 'name': subject.id, 'address_book': 'ASH',
                       'phone': phone, 'email': email}
            self.apptoto.post_contact(contact)
            pass

        if contact_exists:
            phone_numbers = [p.get('normalized') for p in contact.get('phone_numbers')]
            email_addresses = [e.get('address') for e in contact.get('email_addresses')]

            need_to_update = False
            if phone not in phone_numbers:
                logger.info(f'Adding new phone for {subject.id} to apptoto address book')
                need_to_update = True
                for i in range(0, len(phone_numbers)):
                    contact['phone_numbers'][i]['is_primary'] = False
                contact['phone_numbers'].append({'number': phone, 'is_mobile': True, 'is_primary': True})

            if email not in email_addresses:
                logger.info(f'Adding new email for {subject.id} to apptoto address book')
                need_to_update = True
                for i in range(0, len(email_addresses)):
                    contact['email_addresses'][i]['is_primary'] = False
                contact['email_addresses'].append({'address': email, 'is_primary': True})

            if need_to_update:
                updated_contact = {'external_id': subject.id, 'name': subject.id, 'address_book': 'ASH',
                                   'id': contact.get('id'), 'phone_numbers': contact.get('phone_numbers'),
                                   'email_addresses': contact.get('email_addresses')}
                self.apptoto.put_contact(updated_contact)

        self.update_events()
