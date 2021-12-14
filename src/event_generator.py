import random
from collections import namedtuple
from datetime import datetime, timedelta, date, time
from pathlib import Path
from typing import Dict, List
import logging.config
import pandas as pd

from src.mylogging import DEFAULT_LOGGING
from src.apptoto import Apptoto, ApptotoEvent, ApptotoParticipant
from src.constants import DAYS_1, DAYS_2, MESSAGES_PER_DAY_1, MESSAGES_PER_DAY_2
from src.enums import Condition
from src.participant import Participant
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


def _condition_abbrev(condition: Condition) -> str:
    if condition == Condition.VALUES:
        return 'Values'
    elif condition == Condition.HIGHLEVEL:
        return 'HLC'
    elif condition == Condition.DOWNREG:
        return 'CR'
    else:
        assert 'Invalid condition'


def daily_diary_one(config: Dict[str, str], participant: Participant):
    """
    Generate events for the first round of daily diary messages,
    which are sent after session 0, before session 1.
    :return:
    """
    apptoto = Apptoto(api_token=config['apptoto_api_token'], user=config['apptoto_user'])

    if not all(vars(participant).values()):
        missing = ', '.join([x for x in vars(participant) if not vars(participant)[x]])
        logger.error(f'{participant.participant_id} is missing information: {missing}')
        return 'Unable to generate messages due to missing data from apptoto'

    participants = [ApptotoParticipant(participant.initials, participant.phone_number)]

    events = []

    # Diary round 1
    round1_start = date.fromisoformat(participant.session0_date) + timedelta(days=2)
    round1_dates = get_diary_dates(round1_start)
    sleep_time = time.fromisoformat(participant.sleep_time)
    for day, message_date in enumerate(round1_dates):
        content = f'UO: Daily Diary #{day + 1}'
        title = f'ASH Daily Diary #{day + 1}'
        message_datetime = datetime.combine(message_date, sleep_time) - timedelta(hours=2)
        events.append(ApptotoEvent(calendar=config['apptoto_calendar'],
                                   title=title,
                                   start_time=message_datetime,
                                   content=content,
                                   participants=participants))

    if len(events) > 0:
        apptoto.post_events(events)

    return 'Diary round 1 created'


def daily_diary_three(config: Dict[str, str], participant: Participant):
    """
    Generate events for the third round of daily diary messages,
    which are sent after session 2.
    :return:
    """
    apptoto = Apptoto(api_token=config['apptoto_api_token'], user=config['apptoto_user'])

    if not all(vars(participant).values()):
        missing = ', '.join([x for x in vars(participant) if not vars(participant)[x]])
        logger.error(f'{participant.participant_id} is missing information: {missing}')
        return 'Unable to generate messages due to missing data from apptoto'

    participants = [ApptotoParticipant(participant.initials, participant.phone_number)]

    events = []

    # Diary round 3
    round3_start = date.fromisoformat(participant.session2_date) + timedelta(weeks=6)

    round3_dates = get_diary_dates(round3_start)
    sleep_time = time.fromisoformat(participant.sleep_time)
    for day, message_date in enumerate(round3_dates):
        content = f'UO: Daily Diary #{day + 9}'
        title = f'ASH Daily Diary #{day + 9}'
        message_datetime = datetime.combine(message_date, sleep_time) - timedelta(hours=2)
        events.append(ApptotoEvent(calendar=config['apptoto_calendar'],
                                   title=title,
                                   start_time=message_datetime,
                                   content=content,
                                   participants=participants))

    if len(events) > 0:
        apptoto.post_events(events)

    return 'Diary round 3 created'


def generate_messages(config, participant, instance_path):
    """
    Generate events for intervention messages, messages about daily cigarette usage,
    messages for boosters, daily diary rounds 2, 3 and 4.
    :return:
    """
    apptoto = Apptoto(api_token=config['apptoto_api_token'],
                      user=config['apptoto_user'])

    if not all(vars(participant).values()):
        missing = ', '.join([x for x in vars(participant) if not vars(participant)[x]])
        logger.error(f'{participant.participant_id} is missing information: {missing}')
        return 'Unable to generate messages due to missing data from apptoto'

    participants = [ApptotoParticipant(participant.initials, participant.phone_number)]

    events = []
    message_file = Path(instance_path) / config['message_file']
    messages = Messages(message_file)
    num_required_messages = 28 * (MESSAGES_PER_DAY_1 + MESSAGES_PER_DAY_2)
    messages.filter_by_condition(participant.condition, participant.message_values,
                                 num_required_messages)

    quit_date = date.fromisoformat(participant.quit_date)
    wake_time = time.fromisoformat(participant.wake_time)
    sleep_time = time.fromisoformat(participant.sleep_time)

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

        title = f'{_condition_abbrev(participant.condition)} Booster {n}'
        content = "UO: Booster session"
        events.append(Event(time=message_datetime, title=title, content=content))
        n = n + 1

        message_date = quit_date + timedelta(days=(days + 3))
        booster_dates.append(message_date)
        message_datetime = datetime.combine(message_date, sleep_time) - timedelta(hours=3)
        title = f'{_condition_abbrev(participant.condition)} Booster {n}'
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
    logger.info(f'Generating intervention messages for {participant.participant_id}')
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
            apptoto_events.append(ApptotoEvent(calendar=config['apptoto_calendar'],
                                               title=e.title,
                                               start_time=e.time,
                                               content=e.content,
                                               participants=participants))

        apptoto.post_events(apptoto_events)

        csv_path = Path(DOWNLOAD_DIR)
        f = csv_path / (participant.participant_id + '_messages.csv')
        messages.write_to_file(f, columns=['UO_ID', 'Message'])

    return f'Messages written to {participant.participant_id}_messages.csv'


def generate_task_files(config, participant, instance_path):
    message_file = Path(instance_path) / config['message_file']
    csv_path = Path(DOWNLOAD_DIR)
    for session in range(1, 3):
        for run in range(1, 5):
            messages = Messages(message_file)
            messages.filter_by_condition(Condition.VALUES, participant.task_values, TASK_MESSAGES)
            messages.add_column('iti', ITI)
            file_name = csv_path / f'VAFF_{participant.participant_id}_Session{session}_Run{run}.csv'
            messages.write_to_file(file_name, columns=['Message', 'iti'], header=['message', 'iti'])
            logger.info(f'Wrote {file_name.name}')
    return f'Task files created for {participant.participant_id}'


def get_conversations(config, participant, instance_path):
    """Get timestamp and content of all message to and from participant."""
    apptoto = Apptoto(api_token=config['apptoto_api_token'], user=config['apptoto_user'])
    begin = datetime(year=2021, month=4, day=1)
    events = apptoto.get_events(begin=begin.isoformat(),
                                phone_number=participant.phone_number,
                                include_conversations=True)

    conversations = pd.json_normalize(events, record_path=['participants',
                                                           'conversations',
                                                           'messages'],
                                      meta=['title',
                                            'start_time',
                                            'calendar_id',
                                            ['participants', 'event_id']])

    conversations = conversations[conversations.calendar_id == ASH_CALENDAR_ID]
    conversations['start_time'] = pd.to_datetime(conversations['start_time'])

    sent = conversations[conversations.event_type == 'sent']
    sent = sent.sort_values('id').groupby(['participants.event_id']).first()
    message_file = Path(instance_path) / config['message_file']
    messages = pd.read_csv(message_file, dtype=str)
    messages['content'] = 'UO: ' + messages.Message
    sent = sent.merge(messages, on='content', how='left').set_index('start_time')
    replied = conversations[conversations.event_type == 'replied'].set_index('start_time')

    all_convos = sent.join(replied['content'], rsuffix='_reply')
    sms_convos = all_convos[all_convos.title.str.contains(SMS_TITLE)]

    csv_path = Path(DOWNLOAD_DIR)
    sms_name = csv_path / f'{participant.participant_id}_sms_conversations.csv'

    sms_convos.to_csv(sms_name, date_format='%x %X',
                      columns=['UO_ID', 'content', 'content_reply'],
                      header=['UO_ID', 'Sent', 'Reply'])

    cig_convos = all_convos[all_convos.title.str.contains(CIGS_TITLE)]
    cig_name = csv_path / f'{participant.participant_id}_cig_conversations.csv'
    cig_convos.to_csv(cig_name, date_format='%x %X',
                      columns=['UO_ID', 'content', 'content_reply'],
                      header=['UO_ID', 'Sent', 'Reply'])

    return f'Conversations written to {sms_name.name} and {cig_name.name}'


def delete_messages(config, participant):
    apptoto = Apptoto(api_token=config['apptoto_api_token'], user=config['apptoto_user'])
    begin = datetime.now()

    events = apptoto.get_events(begin=begin.isoformat(), phone_number=participant.phone_number)
    event_ids = [e['id'] for e in events if not e.get('is_deleted')
                 and e.get('calendar_id') == ASH_CALENDAR_ID]

    logger.info('Found {} messages from {} events for {}'.format(len(event_ids),
                                                                 len(events),
                                                                 participant.participant_id))

    deleted = 0
    for event_id in event_ids:
        apptoto.delete_event(event_id)
        deleted += 1
        logger.info('Deleted event {}, {} of {}'.format(event_id, deleted, len(event_ids)))

    return f'Deleted {len(event_ids)} messages for {participant.participant_id}'
