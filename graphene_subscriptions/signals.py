from graphene_subscriptions.events import EventNames, ModelSubscriptionEvent


def post_save_subscription(sender, instance, created, **kwargs):
    event = ModelSubscriptionEvent(
        operation=EventNames.CREATED.value if created else EventNames.UPDATED.value,
        instance=instance
    )

    event.send()


def post_delete_subscription(sender, instance, **kwargs):
    event = ModelSubscriptionEvent(
        operation=EventNames.DELETED.value, instance=instance
    )
    event.send()
    event.send()
    event.send()
