import json
from typing import Any

import graphql
from asgiref.sync import async_to_sync
from channels.consumer import SyncConsumer
from channels.generic.websocket import JsonWebsocketConsumer, WebsocketConsumer
from graphene_django.settings import graphene_settings
from reactivex import Observable, Subject
from graphene.types.schema import Schema
from graphene_subscriptions.typings import WsMessage
from graphene_subscriptions.utils import WsOperationTypes

stream = Subject()


class GraphqlSubscriptionConsumer(SyncConsumer):
    groups = None

    def __init__(self, *args, **kwargs):
        if self.groups is None:
            self.groups = []

    @staticmethod
    def decode_json(text_data: dict | str | None) -> WsMessage:
        if text_data is None:
            return {}

        if isinstance(text_data, dict):
            return text_data
        else:
            try:
                return json.loads(text_data)
            except json.JSONDecodeError:
                return text_data

    def _send_result(self, id: str, result: graphql.ExecutionResult):
        errors = result.errors

        self.send(
            {
                'type': 'websocket.send',
                'text': json.dumps(
                    {
                        'id': id,
                        'type': 'data',
                        'payload': {
                            'data': result.data,
                            'errors': list(map(str, errors)) if errors else None,
                        }
                    }
                )
            }
        )

    def send_json(self, message_type: str, **kwargs: Any):
        self.send({'type': message_type, **kwargs})

    def send_error(self, error: str):
        self.send_json('websocket.send', message=error)

    def websocket_connect(self, message: str):
        async_to_sync(self.channel_layer.group_add)(
            'subscriptions',
            self.channel_name
        )
        self.send_json('websocket.accept', subprotocol='graphql-ws')

    def websocket_disconnect(self, message: str):
        self.send_json('websocket.close', code=1000)

    def websocket_receive(self, message: dict[str | Any] | str):
        message = self.decode_json(message['text'])

        request_type = message.get('type')
        text = self.decode_json(message.get('text'))

        match request_type:
            case WsOperationTypes.INITIAL_CONNECTION.value:
                return
            case WsOperationTypes.START_SUBSCRIPTION.value:
                payload: dict[str, Any] = message['payload']
                context = None
                schema: Schema = graphene_settings.SCHEMA

                result = schema.execute(
                    payload['query'],
                    operation_name=payload.get('operationName'),
                    variable_values=payload.get('variables'),
                    context_value=context,
                    root_value=stream
                )

                request_id = message.get('id')

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
