import graphene
from django.db import models
from graphene_django.types import DjangoObjectType
from reactivex import Observable
import reactivex
from graphene_subscriptions.events import EventNames
from tests.models import TestModel


class TestModelType(DjangoObjectType):
    class Meta:
        model = TestModel
        fields = ['id', 'name']


class TestModelSubscription(graphene.ObjectType):
    test_model_created = graphene.Field(TestModelType)

    def resolve_test_model_created(root, info):
        return root.filter(
            lambda event: (
                event.operation == EventNames.CREATED.value
                and isinstance(event.instance, TestModel)
            )
        ).map(lambda event: event.instance)


class TestModelTypeDeletedSubscription(graphene.ObjectType):
    test_model_deleted = graphene.Field(TestModelType, id=graphene.ID())

    def resolve_test_model_deleted(root, info, id):
        return root.filter(
            lambda event: event.operation == EventNames.DELETED.value
            and isinstance(event.instance, TestModel)
            and event.instance.pk == int(id)
        ).map(lambda event: event.instance)


class CustomEventSubscription(graphene.ObjectType):
    test_model_subscription = graphene.String()

    def resolve_test_model_subscription(root, info):
        return root.filter(
            lambda event: event.operation == EventNames.CUSTOM_EVENT.value
        ).map(lambda event: event.instance)


class Subscription(TestModelSubscription, TestModelTypeDeletedSubscription, CustomEventSubscription):
    hello = graphene.String()

    def resolve_hello(root, info):
        return reactivex.of('Hello World!').pipe()


class Query(graphene.ObjectType):
    base = graphene.String()


schema = graphene.Schema(query=Query, subscription=Subscription)
