import smtplib
import unittest
from unittest import mock

from mailbbgun import models
import worker


class FakeMessage():
    def __init__(self):
        self.text = 'test_text'
        self.retries = 0
        self.subject = 'test_subject'
        self.to = 'test@example.com'


class FakeMethod():
    def __init__(self):
        self.delivery_tag = 'test_delivery_tag'


def fake_send_email(email):
    pass


def excepting_send_email(email):
    raise smtplib.SMTPException()


class TestWorker(unittest.TestCase):

    def setUp(self):
        self.worker = worker.MailBBGunWorker()
        self.worker._send_email = fake_send_email
        self.worker._update_message_status = mock.MagicMock()
        self.fake_ch = mock.MagicMock()
        self.fake_method = FakeMethod()
        self.fake_message = FakeMessage()
        self.worker._get_message_by_id = mock.MagicMock(
            return_value=self.fake_message
        )

    def test_process_message_ack(self):
        self.worker.process_message(self.fake_ch, self.fake_method,
                                    object(), b'test_id')
        self.fake_ch.basic_ack.assert_called_with(
            delivery_tag=self.fake_method.delivery_tag
        )

    def test_process_message_deliver_status(self):
        self.worker.process_message(self.fake_ch, self.fake_method,
                                    object(), b'test_id')
        self.worker._update_message_status.assert_called_with(
            self.fake_message, models.Status.delivered
        )

    def test_process_message_increments_retries_on_smtp_failure(self):
        increment_retries = mock.MagicMock()
        schedule_retry = mock.MagicMock()
        self.worker._send_email = excepting_send_email
        self.worker._increment_message_retries = increment_retries
        self.worker._schedule_retry = schedule_retry
        self.worker.process_message(self.fake_ch, self.fake_method,
                                    object(), b'test_id')
        increment_retries.assert_called_with(self.fake_message)
        schedule_retry.assert_called_with('test_id')

    def test_process_message_gives_up_on_max_retries(self):
        increment_retries = mock.MagicMock()
        schedule_retry = mock.MagicMock()
        self.worker._send_email = excepting_send_email
        self.worker._increment_message_retries = increment_retries
        self.worker._schedule_retry = schedule_retry
        self.fake_message.retries = 3
        self.worker.process_message(self.fake_ch, self.fake_method,
                                    object(), b'test_id')
        increment_retries.assert_not_called()
        schedule_retry.assert_not_called()
        self.worker._update_message_status.assert_called_with(
            self.fake_message, models.Status.error
        )
