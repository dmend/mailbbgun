from email.mime import text
import logging
import pika
import smtplib
from sqlalchemy.orm import exc

from mailbbgun import app
from mailbbgun import models


if app.config['DEBUG']:
    logging.basicConfig(level=logging.DEBUG)


_BANNER = """
  __  __       _ _   ____  ____     _____
 |  \/  |     (_) | |  _ \|  _ \   / ____|
 | \  / | __ _ _| | | |_) | |_) | | |  __ _   _ _ __
 | |\/| |/ _` | | | |  _ <|  _ <  | | |_ | | | | '_ \\
 | |  | | (_| | | | | |_) | |_) | | |__| | |_| | | | |
 |_|  |_|\__,_|_|_| |____/|____/   \_____|\__,_|_| |_|

        _  ____________.---------.
        \`'  __________|_________| o o o
        /   (_)__]
       |    |
      .'   .'
      |____]
"""
_DELIVERY_MODE_PERSISTENT = 2
_LOG = logging.getLogger(__name__)


class MailBBGunWorker():

    def configure_rabbitmq(self):
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(app.config['RABBITMQ_HOST'])
        )
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue='mailbbgun', durable=True)
        self.channel.queue_bind(exchange='amq.direct', queue='mailbbgun')

        self.retry_channel = self.connection.channel()
        self.retry_channel.queue_declare(
            queue='retry_delay',
            durable=True,
            arguments={
                'x-message-ttl': app.config['RETRY_DELAY_MS'],
                'x-dead-letter-exchange': 'amq.direct',
                'x-dead-letter-routing-key': 'mailbbgun'
            }
        )

    def process_message(self, ch, method, properties, body):
        message_id = body.decode('UTF-8')
        _LOG.info("Processing message id {}".format(message_id))
        try:
            message = self._get_message_by_id(message_id)
            email = text.MIMEText(message.text)
            email['Subject'] = message.subject
            email['From'] = app.config['FROM_EMAIL']
            email['To'] = message.to
            self._send_email(email)
            self._update_message_status(message, models.Status.delivered)
            _LOG.info("Delivered message id {}".format(message_id))
        except (exc.NoResultFound, exc.MultipleResultsFound):
            _LOG.exception("Fatal database exception on message id {}".format(
                message_id
            ))
        except smtplib.SMTPException:
            if message.retries < app.config['MAX_RETRIES']:
                _LOG.warning(
                    "Failed to deliver message id {}.  Retrying.".format(
                        message_id
                    )
                )
                self._increment_message_retries(message)
                self._schedule_retry(message_id)
            else:
                _LOG.exception(
                    "Failed to deliver message id {}.  Giving up.".format(
                        message_id
                    )
                )
                self._update_message_status(message, models.Status.error)
        finally:
            ch.basic_ack(delivery_tag=method.delivery_tag)

    def _get_message_by_id(self, message_id):
        return models.Message.query.filter(
            models.Message.id == message_id
        ).one()

    def _send_email(self, email):
        # Enable SMTP TLS
        if app.config['SMTP_TLS_ENABLED']:
            SMTP = smtplib.SMTP_SSL
        else:
            SMTP = smtplib.SMTP
        with SMTP(host=app.config['SMTP_HOST'],
                  port=app.config['SMTP_PORT']) as smtp:
            smtp.ehlo()
            smtp.login(app.config['SMTP_USER'],
                       app.config['SMTP_PASSWORD'])
            smtp.send_message(email, from_addr=email['From'],
                              to_addrs=email['To'])

    def _update_message_status(self, message, status):
        message.status = status
        models.db.session.add(message)
        models.db.session.commit()

    def _increment_message_retries(self, message):
        message.retries += 1
        models.db.session.add(message)
        models.db.session.commit()

    def _schedule_retry(self, message_id):
        self.retry_channel.basic_publish(
            exchange='',
            routing_key='retry_delay',
            body=message_id,
            properties=pika.BasicProperties(
                delivery_mode=_DELIVERY_MODE_PERSISTENT
            )
        )


if __name__ == '__main__':
    print(_BANNER)
    print("Waiting for messages. To exit press CTRL+C ...")
    worker = MailBBGunWorker()

    def process_message(ch, method, properties, body):
        worker.process_message(ch, method, properties, body)
    worker.configure_rabbitmq()
    worker.channel.basic_qos(prefetch_count=1)
    worker.channel.basic_consume(process_message, queue='mailbbgun')
    worker.channel.start_consuming()
