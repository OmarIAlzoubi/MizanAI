from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from app.api.activity import (
    get_activity,
)

from app.api.chat import (
    ChatRequest,
    FeedbackRequest,
    handle_chat,
    handle_feedback,
)

from app.api.dashboard import (
    get_dashboard,
)

from app.recipes.learning_repository import (
    LearningRunFeedbackConflictError,
    LearningRunNotFoundError,
)


router = APIRouter()


# =========================================================
# DASHBOARD
# =========================================================


@router.get(
    "/api/dashboard"
)
def dashboard():

    return get_dashboard()


# =========================================================
# CHAT
# =========================================================


@router.post(
    "/chat"
)
def chat(
    request: ChatRequest,
):

    return handle_chat(
        request
    )


# =========================================================
# CHAT FEEDBACK
# =========================================================


@router.post(
    "/chat/feedback"
)
def chat_feedback(
    request: FeedbackRequest,
):

    try:

        return handle_feedback(
            request
        )

    except LearningRunNotFoundError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except LearningRunFeedbackConflictError as exc:

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


# =========================================================
# ACTIVITY
# =========================================================


@router.get(
    "/api/activity"
)
def activity(
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
):

    return get_activity(
        limit=limit
    )