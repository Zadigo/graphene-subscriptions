from channels.routing import URLRouter
import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from graphene_subscriptions.consumers import GraphqlSubscriptionConsumer
from tests.models import TestModel
from django.db.models.signals import post_save, post_delete
from graphene_subscriptions.signals import post_save_subscription, post_delete_subscription


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
async def test_subscription_success():
    """Test that a simple subscription query returns the expected result."""
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
    assert response['payload'] == {
        'data': {
            'hello': 'Hello World!'
        },
        'errors': None
    }
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_subscription_model_creation_sucess():
    post_save.connect(
        post_save_subscription,
        sender=TestModel,
        dispatch_uid='test_model_post_save'
    )

    communicator = WebsocketCommunicator(
        GraphqlSubscriptionConsumer.as_asgi(),
        '/graphql/'
    )
    connected, subprotocol = await communicator.connect()
    assert connected

    subscription = """
    subscription {
        testModelCreated {
            name
        }
    }
    """

    await _query_helper(subscription, communicator)

    item = await sync_to_async(TestModel.objects.create)(name="test name")

    response = await communicator.receive_json_from()
    assert response['payload'] == {
        'data': {
            'testModelCreated': {
                'name': item.name
            }
        },
        'errors': None,
    }

    post_save.disconnect(
        post_save_subscription,
        sender=TestModel,
        dispatch_uid='test_model_post_save'
    )
