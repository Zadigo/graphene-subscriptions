from channels.routing import URLRouter
import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from graphene_subscriptions.consumers import GraphqlSubscriptionConsumer
from tests.models import TestModel


async def _query_helper(query, communicator, variables=None):
    await communicator.send_json_to(
        {
            'id': 1,
            'type': 'start_subscription',
            'payload': {
                'query': query,
                'variables': variables
            }
        }
    )


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_simple_test():
    qs = TestModel.objects.all()
    assert await sync_to_async(qs.count)() == 0


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_grapql_schema_endpoint():
    communicator = WebsocketCommunicator(
        GraphqlSubscriptionConsumer.as_asgi(), '/graphql/')

    connected, subprotocol = await communicator.connect()
    assert connected

    subscription = """
    subscription {
        hello
    }
    """

    await _query_helper(subscription, communicator)
    response = await communicator.receive_json_from()
    print(response)
    assert response['payload'] == {
        'data': {
            'hello': 'hello world!'
        },
        'errors': None
    }
    await communicator.disconnect()
