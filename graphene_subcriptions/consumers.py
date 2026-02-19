import json
from typing import Any

import graphql
from asgiref.sync import async_to_sync
from channels.consumer import SyncConsumer
from reactivex import Observable, Subject
from graphene_django.settings import graphene_settings
from graphene_subcriptions.typings import WsMessage
from graphene_subcriptions.utils import WsOperationTypes

stream = Subject()


class GraphqlSubscriptionConsumer(SyncConsumer):
    def _send_result(self, id: str, result):
        pass

    def send_json(self, message_type: str, **kwargs: Any):
        self.send({'type': message_type, **kwargs})

    def send_error(self, error: str):
        self.send_json('websocket.send', message=error)

    def send(self, message):
        return super().send(message)

    def websocket_connect(self, message: str):
        async_to_sync(self.channel_layer.group_add)(
            'subscriptions',
            self.channel_name
        )

        self.send_json('websocket.accept', subprotocol='graphql-ws')

    def websocket_disconnect(self, message: str):
        self.send_json('websocket.close', code=1000)

    def websocket_receive(self, message: str):
        try:
            data: dict[str, Any] = json.loads(message)
        except (KeyError, json.JSONDecodeError):
            self.send_error('Invalid message format')
            return

        request_type = data.get('type')
        text = data.get('text')

        match request_type:
            case WsOperationTypes.INITIAL_CONNECTION.value:
                return
            case WsOperationTypes.START_SUBSCRIPTION.value:
                payload: dict[str, Any] = data['payload']
                context = None
                schema = graphene_settings.SCHEMA

                result = schema.execute(
                    payload['query'],
                    operation_name=payload.get('operationName'),
                    variables=payload.get('variables'),
                    context=context,
                    root=stream,
                    allow_subscriptions=True,
                )

                request_id = data.get('id')

                if hasattr(result, 'subscribe'):
                    result.subscribe(
                        lambda _result: self._send_result(request_id, _result)
                    )
                else:
                    self._send_result(request_id, result)
            case WsOperationTypes.STOP_SUBSCRIPTION.value:
                return
            case _:
                self.send_error('Unknown message type')
                return

    def signal_fired(self, message: str):
        stream.on_next()
