from datetime import datetime
from typing import List

from src.participant import Participant


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

class ApptotoEvent:
    def __init__(self, calendar: str, title: str, start_time: datetime, end_time: datetime,
                 content: str, participants: List[Participant]):
        """
        Create an ApptotoEvent.

        An ApptotoEvent represents a single event.
        Messages will be sent at `start_time` to all `participants`.

        :param str calendar: Calendar name
        :param str title: Event title
        :param datetime start_time: Start time of event
        :param datetime end_time: End time of event
        :param str content: Message content about event
        :param List[ApptotoParticipants] participants: Participants who will receive message content
        """
        self.calendar = calendar
        self.title = title
        self.start_time = start_time.isoformat()
        self.end_time = end_time.isoformat()
        self.content = content

        self.participants = []
        for participant in participants:
            self.participants.append(ApptotoParticipant(participant.initials, participant.phone))
