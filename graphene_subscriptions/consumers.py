import json
from typing import TYPE_CHECKING, Any, AsyncIterable, Optional

import graphql
from asgiref.sync import async_to_sync
from channels.consumer import SyncConsumer
from graphene.types.schema import Schema
from graphene_django.settings import graphene_settings
from reactivex import Observable, Subject

from graphene_subscriptions.typings import WsMessage
from graphene_subscriptions.utils import (WsOperationTypes,
                                          observable_to_async_iterable,
                                          value_to_async_iterable)

if TYPE_CHECKING:
    from channels.consumer import _ChannelScope

stream = Subject()


class ContextDict:
    def __init__(self, scope: '_ChannelScope'):
        self.scope = scope or {}

    def __getattr__(self, item):
        return self.get(item)

    def get(self, item):
        return self.scope.get(item)


def _graphene_subscribe_field_resolver(root: Subject, info: graphql.GraphQLResolveInfo, **args):
    field_def: graphql.GraphQLField = info.parent_type.fields.get(
        info.field_name
    )

    result: Optional[str | graphql.GraphQLFieldResolver] = None

    if field_def is not None and callable(getattr(field_def, 'resolve', None)):
        result = field_def.resolve(root, info, **args)
    else:
        value = root.get(info.field_name)
        if isinstance(value, dict):
            result = value.get(info.field_name)
        else:
            result = getattr(root, info.field_name, None)

    # Bridge the result to AsyncIterable based on its type
    if isinstance(result, Observable):
        return observable_to_async_iterable(result)
    elif isinstance(result, AsyncIterable):
        return result
    # Plain value (e.g. 'Hello World!') — wrap in a single-item async generator
    return value_to_async_iterable(result)


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
                return {'text': text_data}

    def _send_result(self, id: str, result: graphql.MapAsyncIterator):
        async def resolve_map_async_iterator() -> list[dict[str, Any] | str]:
            container = []
            async for item in result:
                if isinstance(item, graphql.ExecutionResult):
                    container.append({
                        'data': item.data,
                        'errors': list(map(str, item.errors)) if item.errors else None
                    })
            return container

        data = async_to_sync(resolve_map_async_iterator)()

        self.send(
            {
                'type': 'websocket.send',
                'text': json.dumps(
                    {
                        'id': id,
                        'type': 'data',
                        'payload': {
                            'data': data,
                            # 'errors': list(map(str, errors)) if errors else None
                        }
                    }
                )
            }
        )

        # breakpoint()
        # errors = result.errors
        # self.send(
        #     {
        #         'type': 'websocket.send',
        #         'text': json.dumps(
        #             {
        #                 'id': id,
        #                 'type': 'data',
        #                 'payload': {
        #                     'data': result.data,
        #                     'errors': list(map(str, errors)) if errors else None
        #                 }
        #             }
        #         )
        #     }
        # )

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

    def websocket_receive(self, message: dict[str, Any] | str):
        message = self.decode_json(message['text'])

        request_type = message.get('type')
        text = self.decode_json(message.get('text'))

        match request_type:
            case WsOperationTypes.INITIAL_CONNECTION.value:
                return
            case WsOperationTypes.START_SUBSCRIPTION.value:
                payload: dict[str, Any] = message['payload']
                context = ContextDict(self.scope)
                schema: Schema = graphene_settings.SCHEMA

                document = graphql.parse(payload['query'])
                operation = graphql.get_operation_ast(
                    document,
                    payload.get('operationName')
                )
                is_subscription = operation.operation == graphql.OperationType.SUBSCRIPTION

                request_id: str = message.get('id')
                if is_subscription:
                    result = async_to_sync(graphql.subscribe)(
                        schema=schema.graphql_schema,
                        document=document,
                        root_value=stream,
                        context_value=context,
                        variable_values=payload.get('variables'),
                        operation_name=payload.get('operationName'),
                        subscribe_field_resolver=_graphene_subscribe_field_resolver
                    )

                    if hasattr(result, 'subscribe'):
                        result.subscribe(
                            lambda _result: self._send_result(
                                request_id,
                                _result
                            )
                        )
                else:
                    result = schema.execute(
                        payload['query'],
                        operation_name=payload.get('operationName'),
                        variable_values=payload.get('variables'),
                        context_value=context,
                        root_value=stream
                    )

                self._send_result(request_id, result)
            case WsOperationTypes.STOP_SUBSCRIPTION.value:
                return
            case _:
                self.send_error('Unknown message type')
                return

    def signal_fired(self, message: str):
        stream.on_next('')
        stream.on_next('')
        stream.on_next('')
