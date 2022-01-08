try:
    import importlib.metadata as importlib_metadata
except ModuleNotFoundError:
    import importlib_metadata  # type: ignore

import json
import logging
import os
import socket
import urllib.error
import urllib.parse
import urllib.request

# FIXME https://github.com/litl/backoff/issues/104
import backoff  # type: ignore
import capnp  # type: ignore
import click
import pika  # type: ignore

package_name = __spec__.name  # type: ignore
__metadata__ = importlib_metadata.metadata(package_name)  # type: ignore
__version__ = __metadata__["Version"]

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(package_name)

pinboard_post_schema = os.path.dirname(__file__) + "/pinboard_post.capnp"
pinboard_post = capnp.load(pinboard_post_schema)


def fatal_code(ex):
    fatal = True
    if hasattr(ex, "code") and (ex.code < 400 or ex.code == 429):
        fatal = False
    elif isinstance(ex, socket.timeout) or isinstance(ex, urllib.error.URLError):
        fatal = False
    return fatal


def callback(channel, method, properties, body, opener):
    log.info(
        "Received message",
        extra={"message_id": properties.message_id},
    )
    log.debug("Received message", extra={"body": body})

    post = pinboard_post.PinboardPost.from_bytes(body)
    log.debug("Deserialized message", extra={"post": body})
    try:
        archiveorg(opener=opener, url=post.href)
    except urllib.error.HTTPError:
        log.exception("Error when archiving, DLQ:ing", extra={"post": body})
        channel.basic_nack(delivery_tag=method.delivery_tag)
    else:
        channel.basic_ack(delivery_tag=method.delivery_tag)


@backoff.on_exception(
    backoff.constant,
    (urllib.error.HTTPError, urllib.error.URLError, socket.timeout),
    interval=300,
    max_tries=3,
    jitter=None,
    giveup=fatal_code,
)  # pylint: disable=inconsistent-return-statements
def archiveorg(*, opener, url):
    if already_archiveorg(opener=opener, url=url):
        return True
    data = urllib.parse.urlencode({"url": url, "capture_all": "on"})
    data = data.encode("ascii")
    with opener.open(
        "https://web.archive.org/save/%s" % urllib.parse.quote_plus(url),
        data=data,
        timeout=5,
    ) as file:
        if file.status == 200:
            log.info("archive.org'd URL", extra={"url": url})
        else:
            log.info(
                "archive.org reported %s for %s", file.status, url, extra={"url": url}
            )


@backoff.on_exception(
    backoff.constant,
    (urllib.error.HTTPError, urllib.error.URLError, socket.timeout),
    interval=300,
    max_tries=3,
    jitter=None,
    giveup=fatal_code,
)  # pylint: disable=inconsistent-return-statements
def already_archiveorg(*, opener, url):
    data = urllib.parse.urlencode({"url": url})
    with opener.open(
        "https://archive.org/wayback/available?%s" % data,
        timeout=5,
    ) as file:
        response = file.read().decode("utf-8")
        archived = json.loads(response)
        # https://archive.org/help/wayback_api.php
        if archived.get("archived_snapshots"):
            log.info("URL already on archive.org", extra={"url": url})
            return True


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


def cli():
    main(  # pylint: disable=unexpected-keyword-arg,missing-kwoa
        auto_envvar_prefix="PINQUE"
    )


if __name__ == "__main__":
    cli()
