from datetime import datetime
import enum
import json
import uuid

import flask_sqlalchemy as sqlalchemy
from sqlalchemy.dialects import postgresql as pg

from mailbbgun import app


class Status(enum.Enum):
    delivered = 'DELIVERED'
    error = 'ERROR'
    pending = 'PENDING'


class BBJSONEncoder(json.JSONEncoder):
    """Custom JSONEncoder to handle UUIDs and Status enum."""
    def default(self, obj):
        if isinstance(obj, Status):
            return obj.value
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)


app.json_encoder = BBJSONEncoder
db = sqlalchemy.SQLAlchemy(app)


class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(pg.UUID(as_uuid=True), primary_key=True)
    created = db.Column(db.DateTime)
    text = db.Column(db.String(app.config['MAX_TEXT_SIZE']))
    processed = db.Column(db.DateTime)
    retries = db.Column(db.Integer)
    status = db.Column(db.Enum(Status))
    subject = db.Column(db.String(app.config['MAX_SUBJECT_SIZE']))
    to = db.Column(db.String(app.config['MAX_EMAIL_ADDRESS_SIZE']))

    def __init__(self, to, subject, text):
        self.id = uuid.uuid4()
        self.created = datetime.utcnow()
        self.text = text
        self.retries = 0
        self.subject = subject
        self.status = Status.pending
        self.to = to

    def __repr__(self):
        return "Message(to='{}', subject='{}', text='{}')".format(
            self.to, self.subject, self.text
        )

    def api_view(self):
        return {
            "id": self.id,
            "subject": self.subject,
            "status": self.status
        }
