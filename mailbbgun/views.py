import flask
import jsonschema
import logging
import pika

from mailbbgun import app
from mailbbgun import models


if app.config['DEBUG']:
    logging.basicConfig(level=logging.DEBUG)


_DELIVERY_MODE_PERSISTENT = 2
_LOG = logging.getLogger(__name__)


class BadRequestException(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


@app.route('/messages', methods=['POST'])
def new_message():
    data = _validate_message_request()
    _LOG.debug("New message: {}".format(data))

    message = models.Message(**data)
    models.db.session.add(message)

    connection = pika.BlockingConnection(
        pika.ConnectionParameters(app.config['RABBITMQ_HOST'])
    )
    channel = connection.channel()
    channel.queue_declare(queue='mailbbgun', durable=True)
    channel.queue_bind(exchange='amq.direct', queue='mailbbgun')

    work_delay = connection.channel()
    work_delay.queue_declare(
        queue='work_delay',
        durable=True,
        arguments={
            'x-message-ttl': 5000,  # 5 sec delay before sending to worker
            'x-dead-letter-exchange': 'amq.direct',
            'x-dead-letter-routing-key': 'mailbbgun'
        }
    )
    work_delay.basic_publish(
        exchange='',
        routing_key='work_delay',
        body=str(message.id),
        properties=pika.BasicProperties(
            delivery_mode=_DELIVERY_MODE_PERSISTENT
        )
    )
    connection.close()

    response = flask.jsonify(message.api_view())
    response.headers['Location'] = '{}/messages/{}'.format(
        flask.request.host_url.rstrip('/'), message.id
    )
    models.db.session.commit()
    return response, 201


@app.route('/messages', methods=['GET'])
def list_messages():
    limit = flask.request.args.get('limit', app.config['DEFAULT_LIMIT'])
    offset = flask.request.args.get('offset', app.config['DEFAULT_OFFSET'])
    if int(offset) < 0:
        raise BadRequestException("Invalid offset")
    if int(limit) < 0:
        raise BadRequestException("Invalid limit")
    messages = models.Message.query.order_by(
        models.Message.created.desc()
    ).limit(limit).offset(offset).all()
    count = models.Message.query.count()
    return flask.jsonify({
        "messages": [m.api_view() for m in messages],
        "count": count
    })


@app.route('/messages/<message_id>', methods=['GET'])
def get_message(message_id):
    message = models.Message.query.filter(
        models.Message.id == message_id
    ).one_or_none()
    if not message:
        flask.abort(404)
    return flask.jsonify(message.api_view())


def _validate_message_request():
    """Validates message request data

    returns deserialized data if valid."""
    if flask.request.content_type != 'application/json':
        flask.abort(415)
    data = flask.request.get_json()
    if not data:
        raise BadRequestException("Missing request data")
    schema = {
        "type": "object",
        "properties": {
            "to": {"type": "string", "format": "email"},
            "subject": {"type": "string",
                        "maxLength": app.config['MAX_SUBJECT_SIZE']},
            "text": {"type": "string",
                     "maxLength": app.config['MAX_TEXT_SIZE']}
        },
        "required": ["to", "subject", "text"]
    }
    try:
        jsonschema.validate(
            data,
            schema,
            format_checker=jsonschema.FormatChecker()
        )
    except jsonschema.ValidationError:
        raise BadRequestException("Invalid JSON.  Check required properties.")
    return data


@app.errorhandler(BadRequestException)
def bad_request(e):
    response = {
        "error": {
            "status": 400,
            "message": e.message
        }
    }
    return flask.jsonify(response), 400


@app.errorhandler(400)
def bad_request(e):
    response = {
        "error": {
            "status": 400,
            "message": "Bad Request"
        }
    }
    return flask.jsonify(response), 400


@app.errorhandler(404)
def not_found(e):
    response = {
        "error": {
            "status": 404,
            "message": "Not Found"
        }
    }
    return flask.jsonify(response), 404


@app.errorhandler(405)
def method_not_allowed(e):
    response = {
        "error": {
            "status": 405,
            "message": "Method Not Allowed"
        }
    }
    return flask.jsonify(response), 404


@app.errorhandler(415)
def unsupported_media_type(e):
    response = {
        "error": {
            "status": 415,
            "message": "Unsupported Media Type"
        }
    }
    return flask.jsonify(response), 415


@app.errorhandler(500)
def internal_server_error(e):
    response = {
        "error": {
            "status": 500,
            "message": "Internal Server Error"
        }
    }
    return flask.jsonify(response), 500
