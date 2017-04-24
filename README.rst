Mail BB Gun
===========

A baby version of MailGun

Requirements
------------

* Python 3.6
* Docker
* SMTP Server account

Setup
-----

Start docker services.

.. code-block:: bash

    docker-compose up -d

Install Python dependencies.  Using a Virtual Environment is highly recommended.

.. code-block:: bash

   pip install -r requirements.txt

Generate the database password.  Be sure to save it in a safe place.

.. code-block:: bash

    export PG_PASSWORD=$(dd if=/dev/urandom bs=1 count=24 2>/dev/null | hexdump -v -e '/1 "%02X"')
    echo $PG_PASSWORD

Export your SMTP password.

.. code-block:: bash

    export SMTP_PASSWORD=YOUR_SMTP_PASSWORD

Copy the sample config file and update it with relevant SMTP account values for your deployment.

.. code-block:: bash

    cp config.py.sample config.py

Add the mailbbgun user to postgresql.

.. code-block:: bash

   bin/postgresql-create-user

Initialize the mailbbgun database schema.

.. code-block:: bash

    python initdb.py

Run api.py and worker.py

.. code-block:: bash

    python api.py
    python worker.py

Now you should be able to use the API.

.. code-block:: bash

    curl -v http://localhost:5000/messages


Architecture
------------

.. image:: https://rawgit.com/dmend/mailbbgun/dev/img/mailbbgun.svg

Mail BB Gun consists of two processes:

* **api.py** - Flask based RESTful API that accepts message requests.
* **worker.py** - Worker process that sends the messages using an external SMTP server.

All message requests are saved to a PostgreSQL database indefinitely, although
it would be trivial to enforce a shorter retention policy.  We could, for
example, delete messages out of the database after a certain period of time if
database size becomes an issue.

The API sends messages to the worker via a message queue.  The worker also
uses a delay queue that holds retry messages for 10 minutes before putting them
back on the work queue.

There are some known limitations for the service:

* There are no access controls for the API.
* All email originates from a single SMTP account.
* Email is sent in plain text only.
* Email is limited to a single recipient.
* It is possible that a message may be lost if something horrible happens to
  the rabbit queue, although we should be able to query the database for PENDING
  messages and requeue them in case of rabbit disaster.

API
---

POST /messages
~~~~~~~~~~~~~~

Send an email message.

+-----------+---------------------------------+
| Parameter | Description                     |
+===========+=================================+
| to        | Email address of the recipient. |
+-----------+---------------------------------+
| subject   | Message subject.                |
+-----------+---------------------------------+
| text      | Body of the message.            |
+-----------+---------------------------------+

Request
+++++++

.. code-block:: javascript

    POST /messages
    Headers:
        Content-Type: application/json

    Content:
    {
      "to": "someone@example.com",
      "subject": "Example subject",
      "text": "Example text."
    }

Response
++++++++

.. code-block:: javascript

   201 CREATED
   Headers:
     Location: http://localhost:5000/messages/d39aca80-bf8f-42db-9fec-1828cfaf01fd

   Content:
   {
     "id": "d39aca80-bf8f-42db-9fec-1828cfaf01fd",
     "status": "PENDING",
     "subject": "Example subject"
   }

GET /messages
~~~~~~~~~~~~~

Get a list of all messages odered from newest to oldest.  The list
can be paginated by using the `limit` and `offset` parameters.

+-----------+-----------------------------------------------------+
| Parameter | Description                                         |
+===========+=====================================================+
| limit     | Maximum number of messages to return (default: 10). |
+-----------+-----------------------------------------------------+
| offset    | Starting index for the list (default: 0).           |
+-----------+-----------------------------------------------------+

Request
+++++++

.. code-block:: javascript

   GET /messages?offset=0&limit=10
   Headers:
      Accept: application/json

Response
++++++++

.. code-block:: javascript

   200 OK

   Content:
   {
     "messages": [
       {
         "id": "4bef3ffd-d0ad-4037-abf3-062e9ceff507",
         "status": "DELIVERED",
         "subject": "Example subject"
       }
     ],
     "count": 1
   }

GET /messages/{message_id}
~~~~~~~~~~~~~~~~~~~~~~~~~~

Get a single message status.

Request
+++++++

.. code-block:: javascript

   GET /messages/4bef3ffd-d0ad-4037-abf3-062e9ceff507

Response
++++++++

.. code-block:: javascript

   200 OK

   Content:
   {
     "id": "4bef3ffd-d0ad-4037-abf3-062e9ceff507",
     "status": "DELIVERED",
     "subject": "Example subject"
   }
