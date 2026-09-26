export async function fetchDashboard() {

    const response =
        await fetch(
            "/api/dashboard"
        );

    if (!response.ok) {
        throw new Error(
            "Dashboard request failed."
        );
    }

    return response.json();
}


export async function sendChat(
    message
) {

    const response =
        await fetch(
            "/chat",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body:
                    JSON.stringify(
                        {
                            message
                        }
                    )
            }
        );

    if (!response.ok) {
        throw new Error(
            "Chat request failed."
        );
    }

    return response.json();
}


export async function sendFeedback(
    runId,
    helpful
) {

    const response =
        await fetch(
            "/chat/feedback",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body:
                    JSON.stringify(
                        {
                            run_id:
                                runId,

                            helpful
                        }
                    )
            }
        );

    if (!response.ok) {
        throw new Error(
            "Feedback request failed."
        );
    }

    return response.json();
}
