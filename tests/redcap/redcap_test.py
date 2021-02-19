from src.redcap import Redcap, RedcapError
from src.enums import CodedValues
import requests
import pytest

mock_data = [{'rs_id': 'RS999',
              'phone': '555-555-1234',
              'value1_s0': '1',
              'value2_s0': '2',
              'value3_s0': '3',
              'initials': 'ABC',
              'waketime': '07:00',
              'sleeptime': '21:00',
              'condition': '3'}]


class TestRedcap:
    def test_get_participant_phone_invalid(self, requests_mock):
        rc = Redcap(api_token='test token')
        requests_mock.post(url=rc._endpoint,
                           status_code=requests.codes.ok,
                           json=[{'rs_id': 'RS999', 'phone': '555-555-1234'}])

        post = rc.get_participant_phone('Invalid ID')

        assert not post

    def test_get_participant_phone_valid(self, requests_mock):
        rc = Redcap(api_token='test token')
        requests_mock.post(url=rc._endpoint,
                           status_code=requests.codes.ok,
                           json=[{'rs_id': 'RS999', 'phone': '555-555-1234'}])

        post = rc.get_participant_phone('RS999')

        assert post
        assert post == '555-555-1234'

    def test_get_participant_specific_data_invalid(self, requests_mock):
        rc = Redcap(api_token='test token')
        requests_mock.post(url=rc._endpoint,
                           status_code=requests.codes.ok,
                           json=mock_data)

        with pytest.raises(RedcapError):
            rc.get_participant_specific_data('Invalid ID')

    def test_get_participant_specific_data_valid(self, requests_mock):
        rc = Redcap(api_token='test token')
        requests_mock.post(url=rc._endpoint,
                           status_code=requests.codes.ok,
                           json=mock_data)

        part = rc.get_participant_specific_data('RS999')

        assert part.participant_id == 'RS999'
        assert part.values == [CodedValues.humor, CodedValues.relationships, CodedValues.creativity]