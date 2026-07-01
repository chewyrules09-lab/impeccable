import uuid


def new_client_order_id() -> str:
    """Every order gets one of these before it is persisted or sent to a broker.
    Retries must reuse the same ID rather than generating a new one, so the
    persistence layer's primary key constraint can make re-submission a no-op.
    """
    return str(uuid.uuid4())
