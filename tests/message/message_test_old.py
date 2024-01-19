from pathlib import Path

from hypothesis import given, strategies as st

from src.event_generator import MESSAGES_PER_DAY_1, MESSAGES_PER_DAY_2
from src.message import Messages
from src.enums import Condition, CodedValues


# Test that every combination of Condition and CodedValues has enough messages
@given(c=st.sampled_from(Condition),
       v=st.permutations(CodedValues).map(lambda x: x[:3]))
def test_enough_messages(c, v):
    shared_datadir = Path.cwd() / 'instance'
    messages = Messages(path=str(shared_datadir / 'messages.csv'))
    num_required_messages = 28 * (MESSAGES_PER_DAY_1 + MESSAGES_PER_DAY_2)

    messages.filter_by_condition(c, v, num_required_messages)

    assert len(messages) >= num_required_messages

