# this is pycap, not the redcap class originally written for this project
import redcap
from src.apptoto import Apptoto


class RedcapParticipant:
    def __init__(self, subject_id, redcap_token):
        project = redcap.Project(url='https://redcap.uoregon.edu/api/',
                                 token=redcap_token)
        data = project.export_records(events=['session_0_arm_1',
                                              'session_1_arm_1'],
                                      format_type='df')

        self.redcap = data.loc[subject_id].rename(index=dict(session_0_arm_1='s0',
                                                             session_1_arm_1='s1')).transpose()

        # changes to new redcap
        if hasattr(self.redcap.s0, 'date_zs0'):
            self.date_s0 = self.redcap.s0.date_zs0
        else:
            self.date_s0 = self.redcap.s0.date_s0

        if hasattr(self.redcap.s0, 'timezone'):
            self.timezone = self.redcap.s0.timezone
        else:
            self.timezone = 'PT'

        self.id = subject_id
