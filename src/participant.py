# this is pycap, not the redcap class originally written for this project
import redcap
from src.apptoto import Apptoto


class Subject:
    def __init__(self, subject_id, redcap_token):
        project = redcap.Project(url='https://redcap.uoregon.edu/api/',
                                 token=redcap_token)
        data = project.export_records(events=['session_0_arm_1',
                                              'session_1_arm_1',
                                              'session_2_arm_1'],
                                      format='df')
        self.id = subject_id
        self.redcap = data.loc[subject_id].rename(index=dict(session_0_arm_1='s0',
                                                             session_1_arm_1='s1',
                                                             session_2_arm_1='s2')).transpose()
