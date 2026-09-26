import {
    CARD_REGISTRY,
    DEFAULT_ORDER,
    DEFAULT_ENABLED
} from "./cardRegistry.js";

import {
    animateEntrance,
    animateFlip,
    animateVerticalFlip,
    captureRects,
    prefersReducedMotion
} from "./motion.js";


const STORAGE_KEY =
    "mizan.dashboard.layout.v6";

const LEGACY_STORAGE_KEY =
    "mizan.dashboard.layout.v5";


function cards(
    container
) {
    return [
        ...container.querySelectorAll(
            ".card[data-card-id]"
        )
    ];
}


function activeCards(
    container
) {
    return cards(
        container
    )
    .filter(
        card =>
            !card.classList.contains(
                "is-disabled"
            )
    );
}


function enabledIds(
    container
) {
    return activeCards(
        container
    )
    .map(
        card =>
            card.dataset.cardId
    );
}


function defaults() {
    return {
        order:
            [...DEFAULT_ORDER],

        enabled:
            [...DEFAULT_ENABLED],

        sizes:
            Object.fromEntries(
                Object.entries(
                    CARD_REGISTRY
                )
                .map(
                    ([id, config]) => [
                        id,
                        config.defaultSize
                    ]
                )
            )
    };
}


function loadLayout() {
    const fallback =
        defaults();


    const readStorage =
        key => {

            try {

                const raw =
                    localStorage.getItem(
                        key
                    );

                if (!raw) {
                    return null;
                }

                return JSON.parse(
                    raw
                );

            }

            catch {
                return null;
            }
        };


    const current =
        readStorage(
            STORAGE_KEY
        );


    const legacy =
        current
        ?? readStorage(
            LEGACY_STORAGE_KEY
        );


    if (!legacy) {
        return fallback;
    }


    const knownIds =
        Object.keys(
            CARD_REGISTRY
        );


    const rawEnabled =
        Array.isArray(
            legacy.enabled
        )
        ? legacy.enabled
        : [...DEFAULT_ENABLED];


    const enabled =
        rawEnabled.filter(
            id =>
                knownIds.includes(
                    id
                )
        );


    const rawOrder =
        Array.isArray(
            legacy.order
        )
        ? legacy.order
        : fallback.order;


    const order = [
        ...rawOrder.filter(
            id =>
                enabled.includes(
                    id
                )
        ),

        ...enabled.filter(
            id =>
                !rawOrder.includes(
                    id
                )
        )
    ];


    return {
        order,

        enabled,

        sizes: {
            ...fallback.sizes,

            ...(
                legacy.sizes
                && typeof legacy.sizes
                    === "object"
                ? legacy.sizes
                : {}
            )
        }
    };
}


function saveLayout(
    container
) {
    const all =
        cards(
            container
        );

    const active =
        activeCards(
            container
        );


    localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify(
            {
                order:
                    active.map(
                        card =>
                            card.dataset.cardId
                    ),

                enabled:
                    active.map(
                        card =>
                            card.dataset.cardId
                    ),

                sizes:
                    Object.fromEntries(
                        all.map(
                            card => [
                                card.dataset.cardId,
                                card.dataset.size
                            ]
                        )
                    )
            }
        )
    );
}


function applyLayout(
    container,
    layout
) {
    const all =
        cards(
            container
        );


    const byId =
        new Map(
            all.map(
                card => [
                    card.dataset.cardId,
                    card
                ]
            )
        );


    const enabled =
        new Set(
            (
                Array.isArray(
                    layout.enabled
                )
                ? layout.enabled
                : DEFAULT_ENABLED
            )
            .filter(
                id =>
                    byId.has(
                        id
                    )
            )
        );


    const activeOrder = [
        ...layout.order.filter(
            id =>
                enabled.has(
                    id
                )
                && byId.has(
                    id
                )
        ),

        ...DEFAULT_ORDER.filter(
            id =>
                enabled.has(
                    id
                )
                && byId.has(
                    id
                )
                && !layout.order.includes(
                    id
                )
        )
    ];


    for (
        const id
        of activeOrder
    ) {

        const card =
            byId.get(
                id
            );


        const config =
            CARD_REGISTRY[
                id
            ];


        const requested =
            layout.sizes[
                id
            ];


        card.dataset.size =
            config.sizes.includes(
                requested
            )
            ? requested
            : config.defaultSize;


        card.classList.remove(
            "is-disabled"
        );


        container.appendChild(
            card
        );
    }


    for (
        const [
            id,
            card
        ]
        of byId
    ) {

        if (
            enabled.has(
                id
            )
        ) {
            continue;
        }


        const config =
            CARD_REGISTRY[
                id
            ];


        const requested =
            layout.sizes[
                id
            ];


        card.dataset.size =
            config.sizes.includes(
                requested
            )
            ? requested
            : config.defaultSize;


        card.classList.add(
            "is-disabled"
        );


        container.appendChild(
            card
        );
    }
}


function installControls(
    container
) {
    for (
        const card
        of cards(
            container
        )
    ) {
        if (
            card.querySelector(
                ".card-edit-controls"
            )
        ) {
            continue;
        }

        const controls =
            document.createElement(
                "div"
            );

        controls.className =
            "card-edit-controls";

        controls.innerHTML = `
            <button
                class="card-remove-control"
                type="button"
                data-card-remove
                aria-label="إزالة البطاقة من لوحة المعلومات"
                title="إزالة من لوحة المعلومات"
            >×</button>

            <button
                class="card-size-control"
                type="button"
                data-size-step="-1"
                aria-label="تصغير البطاقة"
                title="تصغير"
            >−</button>

            <button
                class="card-drag-handle"
                type="button"
                aria-label="اسحب لإعادة ترتيب البطاقة"
                title="اسحب لإعادة الترتيب"
            >
                <span class="drag-dots"></span>
            </button>

            <button
                class="card-size-control"
                type="button"
                data-size-step="1"
                aria-label="تكبير البطاقة"
                title="تكبير"
            >+</button>
        `;

        card.appendChild(
            controls
        );
    }
}


function syncControls(
    card
) {
    const config =
        CARD_REGISTRY[
            card.dataset.cardId
        ];

    const index =
        config.sizes.indexOf(
            card.dataset.size
        );

    card.querySelector(
        '[data-size-step="-1"]'
    ).disabled =
        index <= 0;

    card.querySelector(
        '[data-size-step="1"]'
    ).disabled =
        index
        >= config.sizes.length - 1;
}


function changeSize(
    container,
    card,
    step
) {
    const config =
        CARD_REGISTRY[
            card.dataset.cardId
        ];

    const index =
        config.sizes.indexOf(
            card.dataset.size
        );

    const nextIndex =
        Math.max(
            0,
            Math.min(
                config.sizes.length - 1,
                index + step
            )
        );

    const next =
        config.sizes[
            nextIndex
        ];

    if (
        next === card.dataset.size
    ) {
        return;
    }

    const all =
        activeCards(
            container
        );

    const before =
        captureRects(
            all
        );

    const beforeCard =
        card.getBoundingClientRect();

    const viewportY =
        beforeCard.top;


    // Important: size change NEVER mutates DOM order.
    card.dataset.size =
        next;

    syncControls(
        card
    );


    requestAnimationFrame(
        () => {
            const afterCard =
                card.getBoundingClientRect();

            // Keep the resized card visually anchored
            // at the same vertical point in the viewport.
            const scrollCorrection =
                afterCard.top
                - viewportY;

            if (
                Math.abs(
                    scrollCorrection
                ) > 0.5
            ) {
                window.scrollBy(
                    0,
                    scrollCorrection
                );
            }
        }
    );


    // During resize we intentionally animate Y only.
    // No sideways FLIP motion = no "page moved left/right" feeling.
    animateVerticalFlip(
        before,
        all,
        {
            skip:
                card,

            duration:
                390
        }
    );


    if (
        !prefersReducedMotion()
    ) {
        card.animate(
            [
                {
                    scale:
                        "0.99"
                },

                {
                    scale:
                        "1.008"
                },

                {
                    scale:
                        "1"
                }
            ],
            {
                duration:
                    360,

                easing:
                    "cubic-bezier(0.22, 1, 0.36, 1)"
            }
        );
    }


    saveLayout(
        container
    );
}


function bindSizeControls(
    container
) {
    for (
        const card
        of cards(
            container
        )
    ) {
        syncControls(
            card
        );

        for (
            const button
            of card.querySelectorAll(
                "[data-size-step]"
            )
        ) {
            button.addEventListener(
                "click",
                event => {
                    event.stopPropagation();

                    changeSize(
                        container,
                        card,
                        Number(
                            button.dataset.sizeStep
                        )
                    );
                }
            );
        }
    }
}


function bindLongPress(
    enterEditMode
) {
    document
        .querySelectorAll(
            ".card[data-card-id]"
        )
        .forEach(
            card => {
                let timer = null;
                let startX = 0;
                let startY = 0;

                const clear = () => {
                    if (timer) {
                        clearTimeout(
                            timer
                        );
                    }

                    timer = null;

                    card.classList.remove(
                        "is-long-pressing"
                    );
                };

                card.addEventListener(
                    "pointerdown",
                    event => {
                        if (
                            document.body
                            .classList
                            .contains(
                                "dashboard-editing"
                            )
                        ) {
                            return;
                        }

                        if (
                            event.target.closest(
                                "button,a,input,textarea"
                            )
                        ) {
                            return;
                        }

                        startX =
                            event.clientX;

                        startY =
                            event.clientY;

                        card.classList.add(
                            "is-long-pressing"
                        );

                        timer =
                            setTimeout(
                                () => {
                                    clear();
                                    enterEditMode();

                                    if (
                                        navigator.vibrate
                                    ) {
                                        navigator.vibrate(
                                            12
                                        );
                                    }
                                },
                                480
                            );
                    }
                );

                card.addEventListener(
                    "pointermove",
                    event => {
                        if (!timer) {
                            return;
                        }

                        const distance =
                            Math.hypot(
                                event.clientX - startX,
                                event.clientY - startY
                            );

                        if (
                            distance > 8
                        ) {
                            clear();
                        }
                    }
                );

                [
                    "pointerup",
                    "pointercancel",
                    "pointerleave"
                ]
                .forEach(
                    type => {
                        card.addEventListener(
                            type,
                            clear
                        );
                    }
                );
            }
        );
}


function bindDragging(
    container
) {
    const indicator =
        document.createElement(
            "div"
        );

    indicator.className =
        "dashboard-drop-indicator";

    document.body.appendChild(
        indicator
    );


    const hideIndicator = () => {
        indicator.classList.remove(
            "is-visible",
            "is-horizontal",
            "is-vertical"
        );
    };


    const distanceToRect = (
        x,
        y,
        rect
    ) => {

        const dx =
            Math.max(
                rect.left - x,
                0,
                x - rect.right
            );

        const dy =
            Math.max(
                rect.top - y,
                0,
                y - rect.bottom
            );

        return Math.hypot(
            dx,
            dy
        );
    };


    const chooseProposal = (
        draggedCard,
        pointerX,
        pointerY
    ) => {

        const all =
            activeCards(
                container
            )
            .filter(
                card =>
                    card
                    !== draggedCard
            );


        if (
            all.length === 0
        ) {
            return null;
        }


        const gridRect =
            container
            .getBoundingClientRect();


        const margin =
            36;


        if (
            pointerX
                < gridRect.left
                - margin
            || pointerX
                > gridRect.right
                + margin
            || pointerY
                < gridRect.top
                - margin
            || pointerY
                > gridRect.bottom
                + margin
        ) {
            return null;
        }


        let target =
            document
            .elementFromPoint(
                pointerX,
                pointerY
            )
            ?.closest(
                ".card[data-card-id]"
            );


        if (
            !target
            || target === draggedCard
            || !container.contains(
                target
            )
        ) {

            target =
                all
                .map(
                    card => ({
                        card,

                        distance:
                            distanceToRect(
                                pointerX,
                                pointerY,
                                card
                                .getBoundingClientRect()
                            )
                    })
                )
                .sort(
                    (
                        a,
                        b
                    ) =>
                        a.distance
                        - b.distance
                )[0]
                ?.card
                ?? null;
        }


        if (!target) {
            return null;
        }


        const rect =
            target
            .getBoundingClientRect();


        const fullWidth =
            target.dataset.size
            === "large";


        const distances = {
            top:
                Math.abs(
                    pointerY
                    - rect.top
                ),

            bottom:
                Math.abs(
                    rect.bottom
                    - pointerY
                ),

            left:
                Math.abs(
                    pointerX
                    - rect.left
                ),

            right:
                Math.abs(
                    rect.right
                    - pointerX
                )
        };


        let edge;


        if (fullWidth) {

            edge =
                distances.top
                <= distances.bottom
                ? "top"
                : "bottom";

        }

        else {

            edge =
                Object.entries(
                    distances
                )
                .sort(
                    (
                        a,
                        b
                    ) =>
                        a[1]
                        - b[1]
                )[0][0];
        }


        /*
           RTL grid semantics:

           top    -> before target
           bottom -> after target
           right  -> before target
           left   -> after target
        */
        const position =
            (
                edge === "top"
                || edge === "right"
            )
            ? "before"
            : "after";


        return {
            target,
            edge,
            position,
            rect
        };
    };


    const drawIndicator = (
        proposal
    ) => {

        if (!proposal) {

            hideIndicator();

            return;
        }


        const {
            rect,
            edge
        } = proposal;


        const inset =
            12;


        indicator.classList.remove(
            "is-horizontal",
            "is-vertical"
        );


        if (
            edge === "top"
            || edge === "bottom"
        ) {

            indicator.classList.add(
                "is-horizontal"
            );


            Object.assign(
                indicator.style,
                {
                    left:
                        `${
                            rect.left
                            + inset
                        }px`,

                    width:
                        `${
                            Math.max(
                                28,
                                rect.width
                                - inset * 2
                            )
                        }px`,

                    top:
                        `${
                            (
                                edge
                                === "top"
                                ? rect.top
                                : rect.bottom
                            )
                            - 2
                        }px`,

                    height:
                        "4px"
                }
            );

        }

        else {

            indicator.classList.add(
                "is-vertical"
            );


            Object.assign(
                indicator.style,
                {
                    top:
                        `${
                            rect.top
                            + inset
                        }px`,

                    height:
                        `${
                            Math.max(
                                28,
                                rect.height
                                - inset * 2
                            )
                        }px`,

                    left:
                        `${
                            (
                                edge
                                === "left"
                                ? rect.left
                                : rect.right
                            )
                            - 2
                        }px`,

                    width:
                        "4px"
                }
            );
        }


        indicator.classList.add(
            "is-visible"
        );
    };


    const maybeAutoScroll = y => {

        const edge =
            92;

        const maxSpeed =
            13;


        if (
            y < edge
        ) {

            const ratio =
                1
                - y / edge;


            window.scrollBy(
                0,
                -maxSpeed
                * ratio
            );

        }

        else if (
            y
            > window.innerHeight
            - edge
        ) {

            const ratio =
                1
                - (
                    window.innerHeight
                    - y
                )
                / edge;


            window.scrollBy(
                0,
                maxSpeed
                * ratio
            );
        }
    };


    container
        .querySelectorAll(
            ".card-drag-handle"
        )
        .forEach(
            handle => {

                handle.addEventListener(
                    "pointerdown",
                    event => {

                        if (
                            !document.body
                            .classList
                            .contains(
                                "dashboard-editing"
                            )
                        ) {
                            return;
                        }


                        if (
                            event.button !== undefined
                            && event.button !== 0
                        ) {
                            return;
                        }


                        event.preventDefault();
                        event.stopPropagation();


                        const card =
                            handle.closest(
                                ".card[data-card-id]"
                            );


                        if (!card) {
                            return;
                        }


                        const startRect =
                            card
                            .getBoundingClientRect();


                        const pointerStartX =
                            event.clientX;

                        const pointerStartY =
                            event.clientY;


                        const ghost =
                            card.cloneNode(
                                true
                            );


                        ghost.classList.add(
                            "dashboard-drag-ghost"
                        );


                        Object.assign(
                            ghost.style,
                            {
                                left:
                                    `${startRect.left}px`,

                                top:
                                    `${startRect.top}px`,

                                width:
                                    `${startRect.width}px`,

                                height:
                                    `${startRect.height}px`,

                                transform:
                                    "translate3d(0,0,0) scale(1.018)"
                            }
                        );


                        document.body.appendChild(
                            ghost
                        );


                        card.classList.add(
                            "is-dragging"
                        );


                        card.style.pointerEvents =
                            "none";


                        document.body.classList.add(
                            "dashboard-dragging"
                        );


                        let latestX =
                            event.clientX;

                        let latestY =
                            event.clientY;

                        let raf =
                            null;

                        let proposal =
                            null;

                        let proposalKey =
                            null;


                        const renderFrame = () => {

                            raf =
                                null;


                            const dx =
                                latestX
                                - pointerStartX;

                            const dy =
                                latestY
                                - pointerStartY;


                            ghost.style.transform =
                                `translate3d(${dx}px, ${dy}px, 0) scale(1.018)`;


                            const next =
                                chooseProposal(
                                    card,
                                    latestX,
                                    latestY
                                );


                            const nextKey =
                                next
                                ? `${
                                    next
                                    .target
                                    .dataset
                                    .cardId
                                }:${
                                    next.position
                                }:${
                                    next.edge
                                }`
                                : null;


                            if (
                                nextKey
                                !== proposalKey
                            ) {

                                proposalKey =
                                    nextKey;


                                proposal =
                                    next;


                                drawIndicator(
                                    proposal
                                );


                                if (
                                    proposal
                                    && event.pointerType
                                    !== "mouse"
                                    && navigator.vibrate
                                ) {

                                    navigator.vibrate(
                                        7
                                    );
                                }
                            }

                            else {

                                proposal =
                                    next;


                                if (proposal) {
                                    drawIndicator(
                                        proposal
                                    );
                                }
                            }
                        };


                        const move =
                            moveEvent => {

                                moveEvent
                                    .preventDefault();


                                latestX =
                                    moveEvent.clientX;

                                latestY =
                                    moveEvent.clientY;


                                if (!raf) {

                                    raf =
                                        requestAnimationFrame(
                                            renderFrame
                                        );
                                }


                                maybeAutoScroll(
                                    latestY
                                );
                            };


                        const cleanup =
                            () => {

                                window.removeEventListener(
                                    "pointermove",
                                    move
                                );


                                window.removeEventListener(
                                    "pointerup",
                                    end
                                );


                                window.removeEventListener(
                                    "pointercancel",
                                    end
                                );


                                if (raf) {

                                    cancelAnimationFrame(
                                        raf
                                    );

                                    raf =
                                        null;
                                }


                                hideIndicator();
                            };


                        const end =
                            async () => {

                                cleanup();


                                const allBefore =
                                    activeCards(
                                        container
                                    );


                                const rectsBefore =
                                    captureRects(
                                        allBefore
                                    );


                                if (
                                    proposal
                                    && proposal.target
                                    && proposal.target
                                    !== card
                                ) {

                                    if (
                                        proposal.position
                                        === "before"
                                    ) {

                                        container.insertBefore(
                                            card,
                                            proposal.target
                                        );

                                    }

                                    else {

                                        proposal.target.after(
                                            card
                                        );
                                    }
                                }


                                card.style.pointerEvents =
                                    "";


                                const allAfter =
                                    activeCards(
                                        container
                                    );


                                animateFlip(
                                    rectsBefore,
                                    allAfter,
                                    {
                                        skip:
                                            card,

                                        duration:
                                            440
                                    }
                                );


                                saveLayout(
                                    container
                                );


                                const finalRect =
                                    card
                                    .getBoundingClientRect();


                                const ghostRect =
                                    ghost
                                    .getBoundingClientRect();


                                const dx =
                                    finalRect.left
                                    - ghostRect.left;

                                const dy =
                                    finalRect.top
                                    - ghostRect.top;


                                if (
                                    !prefersReducedMotion()
                                ) {

                                    const animation =
                                        ghost.animate(
                                            [
                                                {
                                                    transform:
                                                        getComputedStyle(
                                                            ghost
                                                        )
                                                        .transform
                                                },

                                                {
                                                    transform:
                                                        `translate3d(${
                                                            latestX
                                                            - pointerStartX
                                                            + dx
                                                        }px, ${
                                                            latestY
                                                            - pointerStartY
                                                            + dy
                                                        }px, 0) scale(1)`
                                                }
                                            ],

                                            {
                                                duration:
                                                    260,

                                                easing:
                                                    "cubic-bezier(0.22, 1, 0.36, 1)",

                                                fill:
                                                    "forwards"
                                            }
                                        );


                                    try {
                                        await animation.finished;
                                    }

                                    catch {
                                        // Safe if interrupted.
                                    }
                                }


                                ghost.remove();


                                card.classList.remove(
                                    "is-dragging"
                                );


                                document.body.classList.remove(
                                    "dashboard-dragging"
                                );
                            };


                        window.addEventListener(
                            "pointermove",
                            move,
                            {
                                passive:
                                    false
                            }
                        );


                        window.addEventListener(
                            "pointerup",
                            end,
                            {
                                once:
                                    true
                            }
                        );


                        window.addEventListener(
                            "pointercancel",
                            end,
                            {
                                once:
                                    true
                            }
                        );
                    }
                );
            }
        );
}


function updateEmptyState(
    container,
    openGallery
) {
    let empty =
        container.querySelector(
            ".dashboard-empty-state"
        );


    if (!empty) {

        empty =
            document.createElement(
                "div"
            );

        empty.className =
            "dashboard-empty-state";

        empty.innerHTML = `
            <div>
                <strong>
                    لوحة المعلومات فارغة
                </strong>

                <span>
                    أضف البطاقات التي تهمك فقط.
                </span>

                <br>

                <button
                    type="button"
                    data-empty-add
                >
                    ＋ إضافة بطاقة
                </button>
            </div>
        `;


        empty
            .querySelector(
                "[data-empty-add]"
            )
            .addEventListener(
                "click",
                openGallery
            );


        container.appendChild(
            empty
        );
    }


    empty.classList.toggle(
        "is-visible",
        activeCards(
            container
        ).length === 0
    );
}


function removeCard(
    container,
    card,
    {
        renderGallery,
        openGallery
    }
) {
    if (
        card.classList.contains(
            "is-disabled"
        )
    ) {
        return;
    }


    const active =
        activeCards(
            container
        );


    const before =
        captureRects(
            active
        );


    const rect =
        card
        .getBoundingClientRect();


    const ghost =
        card.cloneNode(
            true
        );


    ghost.classList.add(
        "card-removal-ghost"
    );


    Object.assign(
        ghost.style,
        {
            left:
                `${rect.left}px`,

            top:
                `${rect.top}px`,

            width:
                `${rect.width}px`,

            height:
                `${rect.height}px`
        }
    );


    document.body.appendChild(
        ghost
    );


    card.classList.add(
        "is-disabled"
    );


    animateFlip(
        before,
        activeCards(
            container
        ),
        {
            duration:
                420
        }
    );


    if (
        !prefersReducedMotion()
    ) {

        const animation =
            ghost.animate(
                [
                    {
                        opacity: 1,
                        transform:
                            "scale(1)"
                    },

                    {
                        opacity: 0,
                        transform:
                            "scale(0.90)"
                    }
                ],

                {
                    duration:
                        230,

                    easing:
                        "cubic-bezier(0.22, 1, 0.36, 1)",

                    fill:
                        "forwards"
                }
            );


        animation.finished
            .catch(
                () => {}
            )
            .finally(
                () =>
                    ghost.remove()
            );

    }

    else {

        ghost.remove();
    }


    saveLayout(
        container
    );


    renderGallery();


    updateEmptyState(
        container,
        openGallery
    );
}


function addCard(
    container,
    cardId,
    {
        renderGallery,
        openGallery
    }
) {
    const card =
        container.querySelector(
            `.card[data-card-id="${cardId}"]`
        );


    if (
        !card
        || !card.classList.contains(
            "is-disabled"
        )
    ) {
        return;
    }


    const before =
        captureRects(
            activeCards(
                container
            )
        );


    card.classList.remove(
        "is-disabled"
    );


    container.appendChild(
        card
    );


    syncControls(
        card
    );


    animateFlip(
        before,
        activeCards(
            container
        ),
        {
            skip:
                card,

            duration:
                420
        }
    );


    card.classList.remove(
        "is-being-added"
    );


    void card.offsetWidth;


    card.classList.add(
        "is-being-added"
    );


    window.setTimeout(
        () =>
            card.classList.remove(
                "is-being-added"
            ),
        520
    );


    saveLayout(
        container
    );


    renderGallery();


    updateEmptyState(
        container,
        openGallery
    );
}


function bindRemoveControls(
    container,
    helpers
) {
    for (
        const card
        of cards(
            container
        )
    ) {

        const button =
            card.querySelector(
                "[data-card-remove]"
            );


        if (!button) {
            continue;
        }


        button.addEventListener(
            "click",
            event => {

                event.stopPropagation();


                removeCard(
                    container,
                    card,
                    helpers
                );
            }
        );
    }
}


function createWidgetGallery(
    container
) {
    const root =
        document.createElement(
            "div"
        );


    root.className =
        "widget-gallery";


    root.setAttribute(
        "aria-hidden",
        "true"
    );


    root.innerHTML = `
        <div
            class="widget-gallery-backdrop"
            data-gallery-close
        ></div>

        <section
            class="widget-gallery-sheet"
            role="dialog"
            aria-modal="true"
            aria-label="إضافة بطاقة"
        >

            <div
                class="widget-gallery-handle-zone"
                data-gallery-handle
            >
                <span
                    class="widget-gallery-handle"
                    aria-hidden="true"
                ></span>
            </div>

            <header class="widget-gallery-header">

                <div class="widget-gallery-heading">

                    <div class="widget-gallery-title">
                        إضافة بطاقة
                    </div>

                    <div class="widget-gallery-subtitle">
                        اختر البطاقات التي تريد ظهورها في لوحة المعلومات
                    </div>

                </div>

                <button
                    class="widget-gallery-close"
                    type="button"
                    data-gallery-close
                    aria-label="إغلاق"
                >
                    ×
                </button>

            </header>

            <div class="widget-gallery-body">

                <div
                    class="widget-gallery-grid"
                    data-gallery-grid
                ></div>

            </div>

        </section>
    `;


    document.body.appendChild(
        root
    );


    const sheet =
        root.querySelector(
            ".widget-gallery-sheet"
        );


    const grid =
        root.querySelector(
            "[data-gallery-grid]"
        );


    const render = () => {

        const enabled =
            new Set(
                enabledIds(
                    container
                )
            );


        grid.innerHTML =
            Object.entries(
                CARD_REGISTRY
            )
            .map(
                (
                    [
                        id,
                        config
                    ]
                ) => {

                    const added =
                        enabled.has(
                            id
                        );


                    return `
                        <article
                            class="widget-gallery-item"
                            data-gallery-card="${id}"
                        >

                            <div
                                class="widget-gallery-preview"
                                data-accent="${config.accent}"
                            >
                                <div class="widget-preview-content">

                                    <div class="widget-preview-label"></div>

                                    <div class="widget-preview-bars">
                                        <div class="widget-preview-bar"></div>
                                        <div class="widget-preview-bar"></div>
                                        <div class="widget-preview-bar"></div>
                                    </div>

                                </div>
                            </div>

                            <div class="widget-gallery-info">

                                <div class="widget-gallery-copy">

                                    <div class="widget-gallery-name">
                                        ${config.title}
                                        ${
                                            config.isNew
                                            ? '<span class="widget-gallery-new">جديد</span>'
                                            : ''
                                        }
                                    </div>

                                    <div class="widget-gallery-description">
                                        ${config.description}
                                    </div>

                                    <div class="widget-gallery-category">
                                        ${config.category}
                                    </div>

                                </div>

                                <button
                                    class="widget-gallery-action ${
                                        added
                                        ? "is-added"
                                        : ""
                                    }"
                                    type="button"
                                    data-gallery-add="${id}"
                                    ${
                                        added
                                        ? "disabled"
                                        : ""
                                    }
                                >
                                    ${
                                        added
                                        ? "مضاف ✓"
                                        : "إضافة"
                                    }
                                </button>

                            </div>

                        </article>
                    `;
                }
            )
            .join(
                ""
            );


        grid
            .querySelectorAll(
                "[data-gallery-add]"
            )
            .forEach(
                button => {

                    button.addEventListener(
                        "click",
                        () => {

                            addCard(
                                container,
                                button.dataset.galleryAdd,
                                helpers
                            );
                        }
                    );
                }
            );
    };


    let isOpen =
        false;


    const open = () => {

        if (isOpen) {
            return;
        }


        render();


        isOpen =
            true;


        root.classList.add(
            "is-open"
        );


        root.setAttribute(
            "aria-hidden",
            "false"
        );


        document.body
            .classList
            .add(
                "widget-gallery-open"
            );
    };


    const close = () => {

        if (!isOpen) {
            return;
        }


        isOpen =
            false;


        root.classList.remove(
            "is-open"
        );


        root.setAttribute(
            "aria-hidden",
            "true"
        );


        document.body
            .classList
            .remove(
                "widget-gallery-open"
            );


        sheet.style.transform =
            "";
    };


    root
        .querySelectorAll(
            "[data-gallery-close]"
        )
        .forEach(
            element =>
                element.addEventListener(
                    "click",
                    close
                )
        );


    document.addEventListener(
        "keydown",
        event => {

            if (
                event.key === "Escape"
                && isOpen
            ) {
                close();
            }
        }
    );


    const handle =
        root.querySelector(
            "[data-gallery-handle]"
        );


    handle.addEventListener(
        "pointerdown",
        event => {

            if (
                !isOpen
                || (
                    event.button !== undefined
                    && event.button !== 0
                )
            ) {
                return;
            }


            event.preventDefault();


            const startY =
                event.clientY;


            let currentY =
                startY;


            const move =
                moveEvent => {

                    currentY =
                        moveEvent.clientY;


                    const delta =
                        Math.max(
                            0,
                            currentY
                            - startY
                        );


                    sheet.style.transition =
                        "none";


                    sheet.style.transform =
                        `translateY(${delta}px) scale(${
                            Math.max(
                                0.985,
                                1
                                - delta / 7000
                            )
                        })`;
                };


            const end =
                () => {

                    window.removeEventListener(
                        "pointermove",
                        move
                    );


                    window.removeEventListener(
                        "pointerup",
                        end
                    );


                    window.removeEventListener(
                        "pointercancel",
                        end
                    );


                    const delta =
                        Math.max(
                            0,
                            currentY
                            - startY
                        );


                    sheet.style.transition =
                        "";


                    if (
                        delta > 110
                    ) {

                        close();

                    }

                    else {

                        sheet.style.transform =
                            "";
                    }
                };


            window.addEventListener(
                "pointermove",
                move,
                {
                    passive:
                        true
                }
            );


            window.addEventListener(
                "pointerup",
                end,
                {
                    once:
                        true
                }
            );


            window.addEventListener(
                "pointercancel",
                end,
                {
                    once:
                        true
                }
            );
        }
    );


    const helpers = {
        renderGallery:
            render,

        openGallery:
            open
    };


    return {
        open,
        close,
        render,
        helpers
    };
}


function resetLayout(
    container,
    {
        renderGallery,
        openGallery
    }
) {
    const before =
        captureRects(
            activeCards(
                container
            )
        );


    localStorage.removeItem(
        STORAGE_KEY
    );


    const byId =
        new Map(
            cards(
                container
            )
            .map(
                card => [
                    card.dataset.cardId,
                    card
                ]
            )
        );


    for (
        const id
        of DEFAULT_ORDER
    ) {

        const card =
            byId.get(
                id
            );


        if (!card) {
            continue;
        }


        card.dataset.size =
            CARD_REGISTRY[
                id
            ]
            .defaultSize;


        card.classList.remove(
            "is-disabled"
        );


        container.appendChild(
            card
        );


        syncControls(
            card
        );
    }


    animateVerticalFlip(
        before,
        activeCards(
            container
        ),
        {
            duration:
                420
        }
    );


    saveLayout(
        container
    );


    renderGallery();


    updateEmptyState(
        container,
        openGallery
    );
}


export function initDashboardLayout() {
    const container =
        document.getElementById(
            "dashboard-grid"
        );


    const customize =
        document.getElementById(
            "customize-toggle"
        );


    const reset =
        document.getElementById(
            "reset-layout"
        );


    const addWidget =
        document.getElementById(
            "add-widget"
        );


    const hint =
        document.getElementById(
            "edit-hint"
        );


    applyLayout(
        container,
        loadLayout()
    );


    installControls(
        container
    );


    bindSizeControls(
        container
    );


    bindDragging(
        container
    );


    const gallery =
        createWidgetGallery(
            container
        );


    bindRemoveControls(
        container,
        gallery.helpers
    );


    const enterEditMode = () => {

        document.body
            .classList
            .add(
                "dashboard-editing"
            );


        customize.classList.add(
            "is-active"
        );


        customize.textContent =
            "تم";


        hint.setAttribute(
            "aria-hidden",
            "false"
        );
    };


    const exitEditMode = () => {

        gallery.close();


        document.body
            .classList
            .remove(
                "dashboard-editing"
            );


        customize.classList.remove(
            "is-active"
        );


        customize.textContent =
            "تخصيص";


        hint.setAttribute(
            "aria-hidden",
            "true"
        );


        saveLayout(
            container
        );
    };


    customize.addEventListener(
        "click",
        () => {

            if (
                document.body
                .classList
                .contains(
                    "dashboard-editing"
                )
            ) {

                exitEditMode();

            }

            else {

                enterEditMode();
            }
        }
    );


    addWidget.addEventListener(
        "click",
        gallery.open
    );


    reset.addEventListener(
        "click",
        () =>
            resetLayout(
                container,
                gallery.helpers
            )
    );


    bindLongPress(
        enterEditMode
    );


    updateEmptyState(
        container,
        gallery.open
    );


    animateEntrance(
        activeCards(
            container
        )
    );
}
