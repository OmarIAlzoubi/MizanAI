import {
    sendChat,
    sendFeedback
} from "./api.js";


const panel =
    document.getElementById(
        "conversation-panel"
    );

const chat =
    document.getElementById(
        "chat"
    );

const input =
    document.getElementById(
        "chat-input"
    );

const sendButton =
    document.getElementById(
        "send-button"
    );

const collapseButton =
    document.getElementById(
        "conversation-collapse"
    );


const DEBUG_UI =
    new URLSearchParams(
        window.location.search
    )
    .get("debug")
    === "1";


function showConversation() {

    panel.classList.remove(
        "closing"
    );

    panel.classList.add(
        "active"
    );

    document.body.classList.add(
        "chat-open"
    );

    scrollToLatest();
}


function hideConversation() {

    if (
        !panel.classList.contains(
            "active"
        )
    ) {
        return;
    }

    panel.classList.add(
        "closing"
    );

    document.body.classList.remove(
        "chat-open"
    );

    window.setTimeout(
        () => {

            panel.classList.remove(
                "active",
                "closing"
            );
        },
        160
    );
}


function scrollToLatest() {

    requestAnimationFrame(
        () => {

            chat.scrollTop =
                chat.scrollHeight;
        }
    );
}


function addUserMessage(
    text
) {

    showConversation();

    const element =
        document.createElement(
            "div"
        );

    element.className =
        "message user";

    element.textContent =
        text;

    chat.appendChild(
        element
    );

    scrollToLatest();

    return element;
}


function addLoadingMessage() {

    showConversation();

    const element =
        document.createElement(
            "div"
        );

    element.className =
        "message assistant loading";

    element.innerHTML = `
        <div
            class="typing"
            aria-label="MizanAI يكتب"
        >
            <i></i>
            <i></i>
            <i></i>
        </div>
    `;

    chat.appendChild(
        element
    );

    scrollToLatest();

    return element;
}


function hasDebugData(
    debugData
) {

    if (
        !debugData
        || typeof debugData
            !== "object"
    ) {
        return false;
    }

    return Object
        .values(
            debugData
        )
        .some(
            value =>
                value !== null
                && value !== undefined
        );
}


function addAssistantMessage(
    text,
    debugData,
    feedback
) {

    showConversation();

    const container =
        document.createElement(
            "div"
        );

    container.className =
        "message assistant";


    const body =
        document.createElement(
            "div"
        );

    body.textContent =
        text;

    container.appendChild(
        body
    );


    if (
        feedback
        && feedback.requested
        && feedback.run_id
    ) {

        const tools =
            document.createElement(
                "div"
            );

        tools.className =
            "message-tools";


        const like =
            document.createElement(
                "button"
            );

        like.type =
            "button";

        like.className =
            "feedback-button";

        like.textContent =
            "👍";

        like.setAttribute(
            "aria-label",
            "الإجابة مفيدة"
        );


        like.addEventListener(
            "click",
            async () => {

                like.disabled =
                    true;

                try {

                    await sendFeedback(
                        feedback.run_id,
                        true
                    );

                    like.textContent =
                        "✓";
                }

                catch (error) {

                    like.disabled =
                        false;

                    console.error(
                        error
                    );
                }
            }
        );


        tools.appendChild(
            like
        );

        container.appendChild(
            tools
        );
    }


    if (
        DEBUG_UI
        && hasDebugData(
            debugData
        )
    ) {

        const details =
            document.createElement(
                "details"
            );

        details.className =
            "debug";


        const summary =
            document.createElement(
                "summary"
            );

        summary.textContent =
            "التفاصيل التقنية";


        const pre =
            document.createElement(
                "pre"
            );

        pre.textContent =
            JSON.stringify(
                debugData,
                null,
                2
            );


        details.appendChild(
            summary
        );

        details.appendChild(
            pre
        );

        container.appendChild(
            details
        );
    }


    chat.appendChild(
        container
    );

    scrollToLatest();
}


function autoResize() {

    input.style.height =
        "auto";

    input.style.height =
        `${
            Math.min(
                input.scrollHeight,
                140
            )
        }px`;
}


async function submitMessage() {

    const message =
        input.value.trim();

    if (!message) {
        return;
    }


    input.value =
        "";

    autoResize();

    sendButton.disabled =
        true;


    addUserMessage(
        message
    );


    const loading =
        addLoadingMessage();


    try {

        const data =
            await sendChat(
                message
            );

        loading.remove();


        addAssistantMessage(
            data.response
            ?? data.reply
            ?? "تم تنفيذ الطلب.",

            {
                plan:
                    data.plan,

                execution:
                    data.execution,

                routing:
                    data.routing
            },

            data.feedback
            ?? null
        );
    }

    catch (error) {

        loading.remove();

        addAssistantMessage(
            "حدث خطأ أثناء تنفيذ الطلب.",
            null,
            null
        );

        console.error(
            error
        );
    }

    finally {

        sendButton.disabled =
            false;

        input.focus();
    }
}


function bindCardQuestions() {

    document
        .querySelectorAll(
            ".ask-card"
        )
        .forEach(
            button => {

                button.addEventListener(
                    "click",
                    () => {

                        input.value =
                            button
                            .dataset
                            .question
                            ?? "";

                        autoResize();

                        input.focus();
                    }
                );
            }
        );
}


export function initChat() {

    sendButton.addEventListener(
        "click",
        submitMessage
    );


    if (collapseButton) {

        collapseButton.addEventListener(
            "click",
            hideConversation
        );
    }


    input.addEventListener(
        "focus",
        () => {

            if (
                chat.childElementCount
                > 0
            ) {
                showConversation();
            }
        }
    );


    input.addEventListener(
        "pointerdown",
        () => {

            if (
                chat.childElementCount
                > 0
            ) {
                showConversation();
            }
        }
    );


    input.addEventListener(
        "input",
        autoResize
    );


    input.addEventListener(
        "keydown",
        event => {

            if (
                event.key
                === "Enter"
                && !event.shiftKey
            ) {

                event.preventDefault();

                submitMessage();
            }
        }
    );


    bindCardQuestions();

    autoResize();
}