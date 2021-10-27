from datetime import datetime, timedelta


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
        self.quit_date = None
        self.wake_time = None
        self.sleep_time = None
        self.condition = None
        self.message_values = []
        self.task_values = []

    def daily_diary_time(self) -> datetime:
        if self.sleep_time and self.session0_date:
            s = datetime.strptime(f'{self.session0_date} {self.sleep_time}', '%Y-%m-%d %H:%M')
            # First day for daily diary messages is usually 2 days after session 0,
            # 2 hours before normal sleep time.
            # But at least one daily diary must be on the weekend,
            # so if session 0 is on a Saturday, adjust first_day one day after session 0,
            # so the first daily diary is on Sunday.
            # If session 0 is on Sunday, adjust first_day 3 days after session 0,
            # so the last daily diary is on Saturday.
            if s.weekday() == 5:
                first_day = s + timedelta(days=1) - timedelta(hours=2)
            elif s.weekday() == 6:
                first_day = s + timedelta(days=3) - timedelta(hours=2)
            else:
                first_day = s + timedelta(days=2) - timedelta(hours=2)

            return first_day
        else:
            raise ValueError('sleep time or session 0 date not known')


    def _get_start_date(self)