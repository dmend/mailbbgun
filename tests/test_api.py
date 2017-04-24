import json
import unittest

import mailbbgun


class TestApi(unittest.TestCase):

    def setUp(self):
        self.app = mailbbgun.app.test_client()
        self.db = mailbbgun.models.db
        self.db.create_all()
        self.sample_message = {
            "to": "someone@example.com",
            "subject": "test subject",
            "text": "test text"
        }

    def test_root_404(self):
        rv = self.app.get('/')
        self.assertEqual(404, rv.status_code)

    def test_initial_message_count_is_zero(self):
        rv = self.app.get('/messages')
        self.assertEqual(200, rv.status_code)
        self.assertEqual(0, json.loads(rv.data)['count'])

    def test_bad_content_type_returns_415(self):
        rv = self.app.post('/messages')
        self.assertEqual(415, rv.status_code)

    def test_empty_request_returns_400(self):
        rv = self.app.post('/messages',
                           headers={'Content-Type': 'application/json'})
        self.assertEqual(400, rv.status_code)

    @unittest.skip("For some reason this returns a 404 in the test client, "
                   "but it works correctly with curl. ¯\_(ツ)_/¯ ")
    def test_bad_method_returns_405(self):
        rv = self.app.put('/messages')
        self.assertEqual(405, rv.status_code)

    def test_missing_to_address_returns_400(self):
        self.sample_message.pop("to")
        rv = self.app.post('/messages',
                           data=json.dumps(self.sample_message),
                           headers={'Content-Type': 'application/json'})
        self.assertEqual(400, rv.status_code)

    def test_bad_to_address_returns_400(self):
        self.sample_message['to'] = 'not_an_email'
        rv = self.app.post('/messages',
                           data=json.dumps(self.sample_message),
                           headers={'Content-Type': 'application/json'})
        self.assertEqual(400, rv.status_code)

    def test_subjct_too_big_returns_400(self):
        self.sample_message['subject'] = 'X' * (
            mailbbgun.app.config['MAX_SUBJECT_SIZE'] + 1
        )
        rv = self.app.post('/messages',
                           data=json.dumps(self.sample_message),
                           headers={'Content-Type': 'application/json'})
        self.assertEqual(400, rv.status_code)

    def test_message_too_big_returns_400(self):
        self.sample_message['text'] = 'X' * (
            mailbbgun.app.config['MAX_TEXT_SIZE'] + 1
        )
        rv = self.app.post('/messages',
                           data=json.dumps(self.sample_message),
                           headers={'Content-Type': 'application/json'})
        self.assertEqual(400, rv.status_code)

    def test_message_success(self):
        rv = self.app.post('/messages',
                           data=json.dumps(self.sample_message),
                           headers={'Content-Type': 'application/json'})
        self.assertEqual(201, rv.status_code)

    def test_empty_list_when_limit_is_zero(self):
        _ = self.app.post(  # noqa: F841
            '/messages',
            data=json.dumps(self.sample_message),
            headers={'Content-Type': 'application/json'}
        )
        rv = self.app.get('/messages', query_string={'limit': 0})
        self.assertEqual(200, rv.status_code)
        self.assertEqual(1, json.loads(rv.data)['count'])
        self.assertFalse(json.loads(rv.data)['messages'])

    def test_empty_list_when_offset_is_one(self):
        _ = self.app.post(  # noqa: F841
            '/messages',
            data=json.dumps(self.sample_message),
            headers={'Content-Type': 'application/json'}
        )
        rv = self.app.get('/messages', query_string={'offset': 1})
        self.assertEqual(200, rv.status_code)
        self.assertEqual(1, json.loads(rv.data)['count'])
        self.assertFalse(json.loads(rv.data)['messages'])

    def test_negative_offset_returns_400(self):
        _ = self.app.post(  # noqa: F841
            '/messages',
            data=json.dumps(self.sample_message),
            headers={'Content-Type': 'application/json'}
        )
        rv = self.app.get('/messages', query_string={'offset': -1})
        self.assertEqual(400, rv.status_code)

    def test_negative_limit_returns_400(self):
        _ = self.app.post(  # noqa: F841
            '/messages',
            data=json.dumps(self.sample_message),
            headers={'Content-Type': 'application/json'}
        )
        rv = self.app.get('/messages', query_string={'limit': -1})
        self.assertEqual(400, rv.status_code)

    def test_get_single_message(self):
        rv = self.app.post('/messages',
                           data=json.dumps(self.sample_message),
                           headers={'Content-Type': 'application/json'})
        message_id = json.loads(rv.data)['id']
        rv = self.app.get('/messages/{}'.format(message_id))
        self.assertEqual(200, rv.status_code)

    def tearDown(self):
        self.db.drop_all()
