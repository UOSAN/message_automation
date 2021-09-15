import csv
import random
from collections import namedtuple
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from src.apptoto import Apptoto
from src.apptoto_event import ApptotoEvent
from src.constants import DAYS_1, DAYS_2, MESSAGES_PER_DAY_1, MESSAGES_PER_DAY_2
from src.enums import Condition
from src.participant import Participant
from src.message import Messages
from src.constants import DOWNLOAD_DIR

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


def intervals_valid(deltas: List[int]) -> bool:
    """
    Determine if intervals are valid

    :param deltas: A list of integer number of seconds
    :return: True if the interval between each consecutive pair of entries
    to deltas is greater than one hour.
    """
    one_hour = timedelta(seconds=3600)
    for a, b in zip(deltas, deltas[1:]):
        interval = timedelta(seconds=(b - a))
        if interval < one_hour:
            return False

    return True


def random_times(start: datetime, end: datetime, n: int) -> List[datetime]:
    """
    Create randomly spaced times between start and sleep_time.
    :param n:
    :param start: Start time
    :type start: datetime
    :param end: End time
    :type end: datetime
    :param n: Number of times to create
    :return: List of datetime
    """
    delta = end - start
    r = [random.randrange(int(delta.total_seconds())) for _ in range(n)]
    r.sort()

    while not intervals_valid(r):
        r = [random.randrange(int(delta.total_seconds())) for _ in range(n)]
        r.sort()

    times = [start + timedelta(seconds=x) for x in r]
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


def daily_diary(config: Dict[str, str], participant: Participant):
    """
    Generate events for the first round of daily diary messages.

    Generate events for the first round of daily diary messages,
    which are sent after session 0, before session 1.
    :return:
    """
    apptoto = Apptoto(api_token=config['apptoto_api_token'], user=config['apptoto_user'])

    first_day = participant.daily_diary_time()

    events = []
    for day in range(0, 4):
        content = f'UO: Daily Diary #{day + 1}'
        title = f'ASH Daily Diary #{day + 1}'
        t = first_day + timedelta(days=day)
        events.append(ApptotoEvent(calendar=config['apptoto_calendar'],
                                   title=title,
                                   start_time=t,
                                   end_time=t,
                                   content=content,
                                   participants=[participant]))

    # Add quit_message_date date boosters
    s = datetime.strptime(f'{participant.quit_date} {participant.wake_time}', '%Y-%m-%d %H:%M')
    quit_message_date = s + timedelta(hours=3)
    content = 'UO: Quit Date'
    title = 'UO: Quit Date'
    events.append(ApptotoEvent(calendar=config['apptoto_calendar'],
                               title=title,
                               start_time=quit_message_date,
                               end_time=quit_message_date,
                               content=content,
                               participants=[participant]))

    quit_message_date = quit_message_date - timedelta(days=1)
    content = 'UO: Day Before'
    title = 'UO: Day Before'
    events.append(ApptotoEvent(calendar=config['apptoto_calendar'],
                               title=title,
                               start_time=quit_message_date,
                               end_time=quit_message_date,
                               content=content,
                               participants=[participant]))

    if len(events) > 0:
        apptoto.post_events(events)


def generate_messages(config, participant, instance_path):
    """
    Generate events for intervention messages, messages about daily cigarette usage,
    messages for boosters, daily diary rounds 2, 3 and 4.
    :return:
    """
    apptoto = Apptoto(api_token=config['apptoto_api_token'],
                      user=config['apptoto_user'])

    events = []
    message_file = Path(instance_path) / config['message_file']
    messages = Messages(message_file)
    num_required_messages = 28 * (MESSAGES_PER_DAY_1 + MESSAGES_PER_DAY_2)
    messages.filter_by_condition(participant.condition, participant.message_values,
                                 num_required_messages)

    s = datetime.strptime(f'{participant.quit_date} {participant.wake_time}', '%Y-%m-%d %H:%M')
    e = datetime.strptime(f'{participant.quit_date} {participant.sleep_time}', '%Y-%m-%d %H:%M')
    hour_before_sleep_time = e - timedelta(seconds=3600)
    three_hours_before_sleep_time = e - timedelta(hours=3)

    Event = namedtuple('Event', ['time', 'title', 'content'])

    # Generate intervention messages
    n = 0
    for days in range(DAYS_1):
        delta = timedelta(days=days)
        start = s + delta
        end = e + delta
        # Get times each day to send messages
        # Send 5 messages a day for the first 28 days
        times_list = random_times(start, end, MESSAGES_PER_DAY_1)
        for t in times_list:
            # Prepend each message with "UO: " ERROR here
            content = "UO: " + messages[n]
            events.append(Event(time=t, title=SMS_TITLE, content=content))
            n = n + 1

    for days in range(DAYS_1, DAYS_1 + DAYS_2):
        delta = timedelta(days=days)
        start = s + delta
        end = e + delta
        # Get times each day to send messages
        # Send 4 messages a day for the first 28 days
        times_list = random_times(start, end, MESSAGES_PER_DAY_2)
        for t in times_list:
            # Prepend each message with "UO: "
            content = "UO: " + messages[n]
            events.append(Event(time=t, title=SMS_TITLE, content=content))
            n = n + 1

    # Add one message per day asking for a reply with the number of cigarettes smoked
    for days in range(DAYS_1 + DAYS_2):
        delta = timedelta(days=days)
        t = hour_before_sleep_time + delta
        content = "UO: Good evening! Please respond with the number of cigarettes you have smoked today. " \
                  "If you have not smoked any cigarettes, please respond with a 0. Thank you!"
        events.append(Event(time=t, title=CIGS_TITLE, content=content))

    # Add booster messages
    n = 1
    for days in range(1, 51, 7):
        delta = timedelta(days=days)
        t = three_hours_before_sleep_time + delta
        title = f'{_condition_abbrev(participant.condition)} Booster {n}'
        content = "UO: Booster session"
        events.append(Event(time=t, title=title, content=content))
        n = n + 1

        delta = timedelta(days=(days + 3))
        t = three_hours_before_sleep_time + delta
        title = f'{_condition_abbrev(participant.condition)} Booster {n}'
        content = "UO: Booster session"
        events.append(Event(time=t, title=title, content=content))
        n = n + 1

    # Add daily diary messages
    first_day = participant.daily_diary_time()
    for day in range(0, 4):
        content = f'UO: Daily Diary #{day + 5}'
        title = f'ASH Daily Diary #{day + 5}'
        t = first_day + timedelta(days=day + 37)
        events.append(Event(time=t, title=title, content=content))
    for day in range(0, 4):
        content = f'UO: Daily Diary #{day + 9}'
        title = f'ASH Daily Diary #{day + 9}'
        t = first_day + timedelta(days=day + 114)
        events.append(Event(time=t, title=title, content=content))

    if len(events) > 0:
        apptoto_events = []
        for e in events:
            apptoto_events.append(ApptotoEvent(calendar=config['apptoto_calendar'],
                                               title=e.title,
                                               start_time=e.time,
                                               end_time=e.time,
                                               content=e.content,
                                               participants=[participant]))

        apptoto.post_events(apptoto_events)

        csv_path = Path(DOWNLOAD_DIR)
        f = csv_path / (participant.participant_id + '.csv')
        messages.write_to_file(f, columns=['UO_ID', 'Message'])

        # also write events
        events_file = csv_path / (participant.participant_id + '_events.csv')
        with open(events_file, 'w') as ef:
            fieldnames = ['title', 'start_time', 'content']
            writer = csv.DictWriter(ef, fieldnames=fieldnames,
                                    extrasaction='ignore')
            writer.writeheader()
            for event in apptoto_events:
                writer.writerow(event.__dict__)

    return


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

    return "task files created"
