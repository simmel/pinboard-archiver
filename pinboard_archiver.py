try:
    import importlib.metadata as importlib_metadata
except ModuleNotFoundError:
    import importlib_metadata  # type: ignore

import logging
import os
import typing
import urllib.parse
import urllib.request

import capnp  # type: ignore
import click
import pika  # type: ignore

package_name = __spec__.name  # type: ignore
__metadata__ = importlib_metadata.metadata(package_name)
__version__ = __metadata__["Version"]

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(package_name)

pinboard_post_schema = os.path.dirname(__file__) + "/pinboard_post.capnp"
pinboard_post = capnp.load(pinboard_post_schema)


def callback(ch, method, properties, body, opener):
    log.info(
        "Received message",
        extra={"message_id": properties.message_id},
    )
    log.debug("Received message", extra={"body": body})

    post = pinboard_post.PinboardPost.from_bytes(body)
    log.debug("Deserialized message", extra={"post": body})
    httpbin(opener=opener, url=post.href)

    ch.basic_ack(delivery_tag=method.delivery_tag)


def httpbin(*, opener, url):
    data = urllib.parse.urlencode({"url": url})
    data = data.encode("ascii")
    with opener.open("https://httpbin.org/status/429", data=data, timeout=5) as file:
        log.info(file.read().decode("utf-8"))


@click.version_option()
@click.command()
@click.option(
    "--amqp-url",
    required=True,
    show_envvar=True,
    help="URL to AMQP server",
)
def main(*, amqp_url: str):
    """An archiving consumer for Pinboard.in Message Queue"""
    opener = urllib.request.build_opener()
    opener.addheaders = [
        (
            "User-agent",
            "{}/{} (+{})".format(
                __metadata__["Name"],
                __metadata__["Version"],
                __metadata__["Home-page"],
            ),
        )
    ]

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
        on_message_callback=lambda ch, method, properties, body: callback(
            ch, method, properties, body, opener
        ),
    )
    log.info(" [*] Waiting for messages. To exit press CTRL+C")
    channel.start_consuming()
    connection.close()


main(auto_envvar_prefix="PINQUE")
