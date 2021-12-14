# this is pycap, not the redcap class originally written for this project
import redcap

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


class NewParticipant:
    def __init__(self, redcap_token, subject_id):
        project = redcap.Project(url='https://redcap.uoregon.edu/api/',
                                 token=redcap_token)
        data = project.export_records(events=['session_0_arm_1',
                                              'session_1_arm_2',
                                              'session_2_arm_1'],
                                      format='df')
        self.record = data.loc[subject_id].rename(index={'session_0_arm_1': 's0',
                                                         'session_1_arm_2': 's1',
                                                         'session_2_arm_1': 's2'})
