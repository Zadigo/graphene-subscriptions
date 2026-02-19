import enum
from typing import Optional

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.serializers import deserialize
from django.db.models import Model
from django.utils.module_loading import import_string


class EventNames(enum.Enum):
    CREATED = 'created'
    UPDATED = 'updated'
    DELETED = 'deleted'
    CUSTOM_EVENT = 'custom_event'


class BaseEvent:
    def __init__(self, operation: Optional[str] = None, instance: Optional[Model | str] = None):
        self.operation = operation
        self.instance: Optional[Model] = instance

        if instance is not None and type(instance) == str:
            self.instance = deserialize('json', instance)[0].object

        if not isinstance(self.instance, Model):
            raise ValueError('BaseEvent instance value must be a Django model')

    @classmethod
    def from_dict(cls, dict: dict[str, str]) -> "BaseEvent":
        module_name, class_name = dict.get('__class__')
        module = import_string(f"{module_name}.{class_name}")
        klass = getattr(module, class_name)
        return cls(operation=dict.get('operation'), instance=klass)

    def send(self):
        channel_layer = get_channel_layer()
        if channel_layer is not None:
            async_to_sync(channel_layer.group_send)(
                'subscriptions',
                {
                    'type': 'signal.fired',
                    'event': self.to_dict()
                }
            )

    def to_dict(self):
        return {
            'operation': self.operation,
            'instance': self.instance,
            '__class__': (self.__module__, self.__class__.__name__),
        }


class ModelSubscriptionEvent(BaseEvent):
    def __init__(self, operation=None, instance=None):
        super().__init__(operation, instance)

    def to_dict(self):
        data = super().to_dict()
        if self.instance is None:
            raise ValueError(
                'ModelSubscriptionEvent instance value cannot be None'
            )
        data['instance'] = {
            k: v for k, v in self.instance.__dict__.items() if not k.startswith('_')
        }
        return data
