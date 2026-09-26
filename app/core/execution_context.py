from contextlib import contextmanager
from contextvars import ContextVar


_external_message_id: ContextVar[
    str | None
] = ContextVar(
    "external_message_id",
    default=None,
)


def get_external_message_id() -> str | None:

    return _external_message_id.get()


@contextmanager
def external_message_context(
    message_id: str,
):

    token = _external_message_id.set(
        message_id
    )

    try:

        yield

    finally:

        _external_message_id.reset(
            token
        )