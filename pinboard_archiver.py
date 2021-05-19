__version__ = "0.1.0"


import logging
import os
import typing

import capnp  # type: ignore
import click
import pika  # type: ignore

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# pika is too verbose
logging.getLogger("pika.adapters").setLevel(logging.ERROR)

pinboard_post_schema = os.path.dirname(__file__) + "/pinboard_post.capnp"
pinboard_post = capnp.load(pinboard_post_schema)


def callback(ch, method, properties, body):
    log.info(
        "Received message",
        extra={"message_id": properties.message_id},
    )
    log.debug("Received message", extra={"body": body})

    post = pinboard_post.PinboardPost.from_bytes(body)
    log.debug("Deserialized message", extra={"post": body})

    ch.basic_ack(delivery_tag=method.delivery_tag)


@click.command()
@click.option(
    "--amqp-url",
    required=True,
    show_envvar=True,
    help="URL to AMQP server",
)
def main(*, amqp_url: str):
    """An archiving consumer for Pinboard.in Message Queue"""
    connection = pika.BlockingConnection(pika.URLParameters(amqp_url))
    channel = connection.channel()
    channel.basic_qos(prefetch_count=1)
    pinboard_archive = channel.queue_declare(
        queue="pinboard.archive",
        durable=True,
        auto_delete=False,
        arguments={"x-queue-mode": "lazy"},
    )
    channel.queue_bind(
        exchange="pinboard",
        routing_key="pinboard.*",
        queue=pinboard_archive.method.queue,
    )
    channel.basic_consume(
        queue=pinboard_archive.method.queue,
        auto_ack=False,
        on_message_callback=callback,
    )
    log.info(" [*] Waiting for messages. To exit press CTRL+C")
    channel.start_consuming()
    connection.close()


main(auto_envvar_prefix="PINQUE")
