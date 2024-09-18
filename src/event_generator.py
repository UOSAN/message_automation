import random
from collections import namedtuple
from datetime import datetime, timedelta, date, time, timezone
import zoneinfo
from pathlib import Path
from typing import List
import logging.config
import pandas as pd
import numpy as np
import re
import json
import time as tm
import asyncio
import re

from src.mylogging import DEFAULT_LOGGING
from src.apptoto import Apptoto, ApptotoEvent, ApptotoParticipant, ApptotoError
from src.constants import DAYS_1, DAYS_2, MESSAGES_PER_DAY_1, MESSAGES_PER_DAY_2
from src.enums import Condition, CodedValues
from src.participant import RedcapParticipant
from src.message import Messages
from src.constants import DOWNLOAD_DIR, ASH_CALENDAR_ID, TZ_CODES

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


def change_tz(iso_dt: str, tz: str):
    oldtime = datetime.fromisoformat(iso_dt)

    if tz not in TZ_CODES:
        raise ValueError('time zone code not supported')
    newtime = oldtime.replace(tzinfo=zoneinfo.ZoneInfo(TZ_CODES[tz]))

    return newtime


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

    # this file is created, but I never implemented its usage.
    # This would replace searching all events by contact phone number
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

    # See above comment -- I never switched things over to use this
    # leaving it here in case we decide we need to
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
        check_fields(subject, ['initials', 'phone', 'sleeptime', 'email'])

        # update the contact if needed
        self.update_contact()

        participants = [ApptotoParticipant(subject.redcap.s0.initials,
                                           subject.redcap.s0.phone,
                                           subject.redcap.s0.email)]

        events = []

        # Diary round 1
        round1_start = date.fromisoformat(subject.redcap.s0.date_zs0) + timedelta(days=2)
        round1_dates = get_diary_dates(round1_start)
        sleep_time = time.fromisoformat(subject.redcap.s0.sleeptime)

        for day, message_date in enumerate(round1_dates):
            content = f'UO: Daily Diary #{day + 1}'
            title = f'ASH Daily Diary #{day + 1}'
            message_datetime = datetime.combine(message_date, sleep_time) - timedelta(hours=2)
            print(message_datetime)
            events.append(ApptotoEvent(calendar=self.config['apptoto_calendar'],
                                       title=title,
                                       start_time=message_datetime,
                                       time_zone=subject.redcap.s0.timezone,
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

        # update the contact if needed
        self.update_contact()

        participants = [ApptotoParticipant(subject.redcap.s0.initials,
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
            print(message_datetime)
            events.append(ApptotoEvent(calendar=self.config['apptoto_calendar'],
                                       title=title,
                                       start_time=message_datetime,
                                       time_zone=subject.redcap.s0.timezone,
                                       content=content,
                                       participants=participants))

        if len(events) > 0:
            posted_events = self.apptoto.post_events(events)
            self._update_events_file(posted_events)

        return 'Diary round 3 created'

    def generate_messages(self, upload=True):
        """
        Generate events for intervention messages, messages about daily cigarette usage,
        messages for boosters, daily diary rounds 2, 3 and 4.
        :return:
        """
        subject = RedcapParticipant(self.participant_id,
                                    self.config['redcap_api_token'])

        # first check that we have the required info from redcap
        check_fields(subject, ['value1_s0', 'value2_s0', 'initials', 'phone',
                               'sleeptime', 'waketime', 'email'])

        if 's1' not in subject.redcap or pd.isnull(subject.redcap.s1.quitdate):
            return f'Missing quit date for {subject.id}'

        # update the contact if needed
        self.update_contact()

        participants = [ApptotoParticipant(subject.redcap.s0.initials,
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

        quit_date = date.fromisoformat(subject.redcap.s1.quitdate)
        wake_time = time.fromisoformat(subject.redcap.s0.waketime)
        sleep_time = time.fromisoformat(subject.redcap.s0.sleeptime)

        Event = namedtuple('Event', ['time', 'title', 'content'])

        # Add quit_message_date date boosters 3 hrs after wake time
        message_datetime = datetime.combine(quit_date - timedelta(days=1),
                                            wake_time) + timedelta(hours=3)
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
            # if message_date == quit_date:
            #     start_time = datetime.combine(message_date, wake_time) + timedelta(hours=4)
            # else:
            #     start_time = datetime.combine(message_date, wake_time)

            # if message_date in booster_dates:
            #     end_time = datetime.combine(message_date, sleep_time) - timedelta(hours=4)
            # elif message_date in round2_dates:
            #     end_time = datetime.combine(message_date, sleep_time) - timedelta(hours=3)
            # else:
            #     end_time = datetime.combine(message_date, sleep_time) - timedelta(hours=2)

            (start_time, end_time) = self.make_intervention_startend(message_date, subject, booster_dates, round2_dates)
            
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

        if len(events) > 0 and upload:
            apptoto_events = []
            for e in sorted(events):
                apptoto_events.append(ApptotoEvent(calendar=self.config['apptoto_calendar'],
                                                   title=e.title,
                                                   start_time=e.time,
                                                   content=e.content,
                                                   participants=participants,
                                                   time_zone=subject.redcap.s0.timezone))

            posted_events = self.apptoto.post_events(apptoto_events)
            self._update_events_file(posted_events)

            csv_path = Path(DOWNLOAD_DIR)
            if not csv_path.exists():
                csv_path.mkdir()
            f = csv_path / (subject.id + '_messages.csv')
            messages.write_to_file(f, columns=['UO_ID', 'Message'])

        return f'Messages written to {subject.id}_messages.csv'

    def make_intervention_startend(self, message_date, subject, booster_dates, round2_dates):
        quit_date = date.fromisoformat(subject.redcap.s1.quitdate)
        wake_time = time.fromisoformat(subject.redcap.s0.waketime)
        sleep_time = time.fromisoformat(subject.redcap.s0.sleeptime)
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
        return (start_time, end_time)

    def generate_task_files(self):
        subject = RedcapParticipant(self.participant_id,
                                    self.config['redcap_api_token'])
        # first check that we have the required info from redcap
        check_fields(subject, ['value1_s0', 'value7_s0'])

        csv_path = Path(DOWNLOAD_DIR)
        if not csv_path.exists():
            csv_path.mkdir(parents=True)
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
        events = self.apptoto.get_events_by_contact(begin,
                                                    external_id=self.participant_id,
                                                    calendar_id=ASH_CALENDAR_ID,
                                                    include_conversations=True)

        # potential "new" way, not currently possible
        # event_ids = self._get_event_ids()
        # logger.info(f'Searching {len(event_ids)} events')
        # events = self.apptoto.get_events(event_ids, begin=begin, include_conversations=True)

        conversations = pd.json_normalize(events, record_path=['participants',
                                                               'conversations',
                                                               'messages'],
                                          meta=['title',
                                                'start_time',
                                                'calendar_id',
                                                ['participants', 'event_id']])

        csv_path = Path(DOWNLOAD_DIR)
        if conversations.empty:
            return f'No conversatinos found for {self.participant_id}.'

        conversations = conversations[conversations.calendar_id == ASH_CALENDAR_ID]
        conversations['start_time'] = pd.to_datetime(conversations['start_time'])

        messages = pd.read_csv(self.message_file, dtype=str)
        messages['content'] = 'UO: ' + messages.Message
        conversations = conversations.merge(messages, on='content', how='left').set_index('id')

        conversations['at'] = pd.to_datetime(conversations['at'])

        # for debugging only
        # conversations.to_csv(csv_path / f'{self.participant_id}_all_conversations.csv', date_format='%x %X')

        sent = conversations[conversations.event_type == 'sent'].dropna(axis=1, how='all')
        received = conversations[conversations.event_type == 'replied'].dropna(axis=1, how='all')
        if 'UO_ID' in received.columns:  # temporary fix
            received = received.drop(columns=['UO_ID'])

        if sent.empty:
            return f'No messages sent for {self.participant_id}.'

        elif received.empty:
            merged = sent.rename(columns={'at': 'at_sent', 'content': 'content_sent', 'title': 'title_sent'})
            merged['at_rec'] = pd.NaT
            merged['content_rec'] = np.NaN

        else:
            merged = sent.merge(received, on='participants.event_id', suffixes=('_sent', '_rec'), how='outer')

        if 'UO_ID' not in merged.columns:
            merged['UO_ID'] = np.NaN

        columns = ['at_sent', 'UO_ID', 'content_sent', 'at_rec', 'content_rec']
        header = ['sent_at', 'UO_ID', 'message', 'replied_at', 'reply']

        sms_convos = merged[(merged.title_sent.str.contains(SMS_TITLE)) & (~merged.UO_ID.isna())]

        sms_name = csv_path / f'{self.participant_id}_sms_conversations.csv'

        sms_convos.to_csv(sms_name, date_format='%x %X', columns=columns, header=header, index=False)

        cig_convos = merged[(merged.title_sent.str.contains(CIGS_TITLE)) & (merged.content_sent.str.startswith('UO'))]
        cig_name = csv_path / f'{self.participant_id}_cig_conversations.csv'
        cig_convos.to_csv(cig_name, date_format='%x %X', columns=columns, header=header, index=False)

        sms_sent = len(sms_convos['participants.event_id'].unique())
        sms_rec = len(sms_convos[~sms_convos.content_rec.isnull()]['participants.event_id'].unique())
        cig_sent = len(cig_convos['participants.event_id'].unique())
        cig_rec = len(cig_convos[~cig_convos.content_rec.isnull()]['participants.event_id'].unique())

        with np.errstate(divide='ignore', invalid='ignore'):
            response_rate = 100 * np.divide((sms_rec + cig_rec), (sms_sent + cig_sent))
            cig_rr = 100 * np.divide(cig_rec, cig_sent)
            sms_rr = 100 * np.divide(sms_rec, sms_sent)

        with open(csv_path / f'{self.participant_id}_summary.txt', 'w') as f:
            f.write(f'SMS messages sent: {sms_sent}\n')
            f.write(f'SMS replies: {sms_rec}\n')
            f.write(f'SMS response rate: {sms_rr:.02f}\n')
            f.write(f'CIG messages sent: {cig_sent}\n')
            f.write(f'CIG replies: {cig_rec}\n')
            f.write(f'CIG response rate: {cig_rr:.02f}\n')
            f.write(f'Overall response rate: {response_rate:.02f}\n')

        logger.info(f'Conversations written to {sms_name.name} and {cig_name.name}.')
        logger.info(f'Summary written to {self.participant_id}_summary.txt.')

        if np.isnan(response_rate):
            message = f'No conversations started for {self.participant_id}.'
        else:
            message = f'Response rate for {self.participant_id}: {response_rate:.0f}%.'
        return message

    def delete_messages(self):

        begin = datetime.today() + timedelta(days=1)
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

        # this would be another way, never implemented
        """event_ids = self._get_event_ids()
          events = []
        for e_id in event_ids:
            events.append(self.apptoto.get_event(e_id))
        events = [e for e in events if datetime.fromisoformat(e['start_time']) > begin]"""

        events = self.apptoto.get_events_by_contact(begin,
                                                    external_id=self.participant_id,
                                                    calendar_id=ASH_CALENDAR_ID)

        if not events:
            return f'No future events for subject {subject.id}'

        e_df = pd.DataFrame.from_records(events)
        e_df.drop_duplicates(subset='id', inplace=True)

        e_df.rename(columns={'calendar_name': 'calendar'}, inplace=True)
        e_df.drop(columns='is_deleted', inplace=True)

        phone = normalize_phone(subject.redcap.s0.phone)
        email = subject.redcap.s0.email
        initials = subject.redcap.s0.initials

        #TESTING
        #subject.redcap.s0.timezone = 'ET'
        #e_df['title'] = 'test update'
        #print(e_df.start_time)
        #e_df.start_time = [datetime.fromisoformat(x) - timedelta(hours=5) for x in e_df.start_time]

        # As far as I can tell, apptoto will NOT actually change the times when you put the events
        # So this currently does not do anything
        e_df.start_time = [change_tz(x, subject.redcap.s0.timezone) for x in e_df.start_time]
        e_df.end_time = [change_tz(x, subject.redcap.s0.timezone) for x in e_df.end_time]

        # check email, phone against new values
        e_df['phone'] = [p[0]['normalized_phone'] for p in e_df.participants]
        e_df['email'] = [p[0]['email'] for p in e_df.participants]

        # originally we only changed if the phone/email changed, but we need to change the name too
        # and time zone so just update all of them
        # e_df = e_df[(e_df.phone != phone) | (e_df.email != email)]
        e_df.drop(columns=['phone', 'email'], inplace=True)
        new_participant = {'name': initials, 'phone': phone, 'email': email, 'contact_external_id': subject.id}
        e_df['participants'] = [[new_participant] for i in range(0, len(e_df))]
        updated_events = e_df.to_dict(orient='records')

        self.apptoto.put_events(updated_events)

        return f'Updated {len(updated_events)} events for subject {subject.id}'
    
    async def update_times(self):
        subject = RedcapParticipant(self.participant_id,
                                    self.config['redcap_api_token'])
        
        quit_date = date.fromisoformat(subject.redcap.s1.quitdate)
        wake_time = time.fromisoformat(subject.redcap.s0.waketime)
        sleep_time = time.fromisoformat(subject.redcap.s0.sleeptime)
        
        begin = datetime.combine(date.today() + timedelta(days=1), time(0, 0, 0))

        events = self.apptoto.get_events_by_contact(begin,
                                                    external_id=self.participant_id,
                                                    calendar_id=ASH_CALENDAR_ID)

        if not events:
            return f'No future events for subject {subject.id}'

        cleanup_task = asyncio.create_task(self.cleanup_old_messages(events))

        e_df = pd.DataFrame.from_records(events)
        e_df.drop_duplicates(subset='id', inplace=True)
        e_df.drop(columns='is_deleted', inplace=True)
        e_df.drop(columns="end_time", inplace=True)
        e_df.drop(columns="id", inplace=True)
        events.clear()

        intervention_df = e_df[e_df["title"] == "ASH SMS"]
        nonintervention_df = e_df[e_df["title"] != "ASH SMS"]
        #booster_df = e_df[e_df["title"].str.contains("Booster")]
        booster_dates = e_df[e_df["title"].str.contains("Booster")]["start_time"].apply(lambda date: self.get_date(date)).to_list()
        #round2_df = e_df[e_df["title"] == "ASH Daily Diary"]
        round2_dates = e_df[e_df["title"] == "ASH Daily Diary"]["start_time"].apply(lambda date: self.get_date(date)).to_list()

        nonintervention_df["start_time"] = nonintervention_df.apply(lambda event: self.get_new_time(event=event, quit_date=quit_date, 
                                                                                                    wake_time=wake_time, sleep_time=sleep_time), axis=1)
        events.extend(nonintervention_df.to_list())

        #make dates easy to read, then convert to list, split into sublists based on matching days, randomly space every sublist, recombine into big list
        intervention_df["start_time"] = intervention_df.apply(lambda event: self.get_intervention_time(), axis=1)
        events.extend(intervention_df.to_list())

        await cleanup_task

        self.apptoto.post_events(events)

        return f'Updated timing of {len(events)} events for subject {subject.id}'

    async def cleanup_old_messages(self, events):
        for e in events:
            self.apptoto.delete_event(e.id)
        return

    def get_new_time(self, event, quit_date, wake_time, sleep_time):

        title = event["title"]
        message_date = self.get_date(event["start_time"])

        if (re.search("UO: Day Before", title)): 
            return datetime.combine(quit_date - timedelta(days=1), wake_time) + timedelta(hours=3)
        elif (re.search("UO: Quite Date", title)):
            return datetime.combine(quit_date, wake_time) + timedelta(hours=3)
        elif (re.search("ASH CIGS", title)):
            return datetime.combine(message_date, sleep_time) - timedelta(hours=1)
        elif (re.search("Booster \d+$", title)):
            return datetime.combine(message_date, sleep_time) - timedelta(hours=3)
        elif (re.search("ASH Daily Diary", title)):
            return datetime.combine(message_date, sleep_time) - timedelta(hours=2)
        
    async def get_intervention_time(self, events_df, event, subject, booster_dates, round2_dates):
        (start_time, end_time) = self.make_intervention_startend(self.get_date(event.start_time), 
                                                                 subject, booster_dates, round2_dates)
        return 0

    def get_date(input):
        #gets the date portion of the string for the datetime of an apptoto event
        return datetime.strptime(re.split('-\d+:\d+$', re.sub('T', ' ', input[2:]))[0], '%y-%m-%d %H:%M:%S').date()

    # do we need to check primary phone/email?
    def update_contact(self, update_events=False):

        subject = RedcapParticipant(self.participant_id,
                                    self.config['redcap_api_token'])

        if isinstance(subject.redcap.s0.phone, str):
            phone = normalize_phone(subject.redcap.s0.phone)
        else:
            phone = ''
        email = subject.redcap.s0.email
        initials = subject.redcap.s0.initials

        contact_exists = False
        try:
            contact = self.apptoto.get_contact(external_id=subject.id)
            contact_exists = True
        except ApptotoError:
            logger.info(f'Adding {subject.id} to apptoto address book')
            contact = {'external_id': subject.id, 'name': initials, 'address_book': 'ASH',
                       'phone': phone, 'email': email}
            self.apptoto.post_contact(contact)
            pass

        if contact_exists:
            phone_numbers = [p.get('normalized') for p in contact.get('phone_numbers')]
            email_addresses = [e.get('address') for e in contact.get('email_addresses')]
            contact_name = contact['name']
            # do we need to update events for this contact?
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

            ## these have been dealt with and shouldn't exist anymore
            #if contact_name == subject.id:
            #    logger.info(f'Changing name to initials {initials} for {subject.id} in apptoto address book')
            #    if isinstance(initials, str):
            #        contact_name = initials
            #        need_to_update = True
            #   else:
            #        return 

            if need_to_update:
                updated_contact = {'external_id': subject.id, 'name': contact_name, 'address_book': 'ASH',
                                   'id': contact.get('id'), 'phone_numbers': contact.get('phone_numbers'),
                                   'email_addresses': contact.get('email_addresses')}
                self.apptoto.put_contact(updated_contact)

            if need_to_update or update_events:
                self.update_events()
