import asyncio
import enum
from typing import Any, AsyncIterable

from reactivex import Observable


class WsOperationTypes(enum.Enum):
    INITIAL_CONNECTION = "initial_connection"
    START_SUBSCRIPTION = "start_subscription"
    STOP_SUBSCRIPTION = "stop_subscription"
    SUBSCRIBE = "subscribe"


async def observable_to_async_iterable(observable: Observable) -> AsyncIterable:
    queue = asyncio.Queue()
    DONE = object()  # sentinel

    def on_next(value):
        queue.put_nowait(value)

    def on_error(error):
        queue.put_nowait(error)

    def on_completed():
        queue.put_nowait(DONE)

    observable.subscribe(
        on_next=on_next,
        on_error=on_error,
        on_completed=on_completed,
    )

    while True:
        item = await queue.get()
        if item is DONE:
            return
        if isinstance(item, Exception):
            raise item
        yield item


async def value_to_async_iterable(value: Any) -> AsyncIterable:
    yield value
