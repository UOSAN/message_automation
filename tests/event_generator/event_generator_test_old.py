from src.event_generator import intervals_valid, random_times
from datetime import datetime


def test_intervals_valid_empty_list():
    intervals = []
    valid = intervals_valid(intervals)

    assert valid


def test_intervals_valid_intervals_too_short():
    intervals = [100, 200, 300]
    valid = intervals_valid(intervals)

    assert (not valid)


def test_intervals_valid_intervals_valid():
    intervals = [100, 20000, 30000]
    valid = intervals_valid(intervals)

    assert valid


def test_random_times():
    start = datetime(year=2021, month=1, day=1, hour=1)
    end = datetime(year=2021, month=1, day=1, hour=11)
    n = 5

    times = random_times(start, end, n)

    assert (len(times) == n)
