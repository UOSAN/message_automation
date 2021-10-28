from datetime import datetime


class Participant:
    def __init__(self, identifier: str = '', phone: str = ''):
        """
        A single participant to the study, that will receive messages

        :param identifier: The participant identifier, in the format ASH%3d (ASH followed by three digits)
        :type identifier: str
        :param phone: Phone number
        :type phone: str
        """
        self.participant_id = identifier
        self.initials = ''
        self.phone_number = phone
        self.session0_date = None
        self.session1_date = None
        self.session2_date = None
        self.quit_date = None
        self.wake_time = None
        self.sleep_time = None
        self.condition = None
        self.message_values = []
        self.task_values = []

    # functions to get date attributes as datetime objects
    def get_session0_date(self):
        return datetime.strptime(f'{self.session0_date} {self.sleep_time}', '%Y-%m-%d %H:%M')

    def get_session1_date(self):
        return datetime.strptime(f'{self.session1_date} {self.sleep_time}', '%Y-%m-%d %H:%M')

    def get_quit_date(self):
        return datetime.strptime(f'{self.quit_date} {self.sleep_time}', '%Y-%m-%d %H:%M')

    def get_session2_date(self):
        return datetime.strptime(f'{self.session2_date} {self.sleep_time}', '%Y-%m-%d %H:%M')