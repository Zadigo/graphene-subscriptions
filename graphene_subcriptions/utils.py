import enum


class WsOperationTypes(enum.Enum):
    INITIAL_CONNECTION = "initial_connection"
    START_SUBSCRIPTION = "start_subscription"
    STOP_SUBSCRIPTION = "stop_subscription"
    SUBCRIBE = "subscribe"
