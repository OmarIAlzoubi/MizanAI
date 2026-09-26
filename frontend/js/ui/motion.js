const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

export function prefersReducedMotion() {
    return reduceMotion.matches;
}

export function captureRects(elements) {
    const rects = new Map();
    for (const element of elements) rects.set(element, element.getBoundingClientRect());
    return rects;
}

export function animateFlip(previousRects, elements, { skip = null, duration = 420 } = {}) {
    if (prefersReducedMotion()) return;
    requestAnimationFrame(() => {
        for (const element of elements) {
            if (element === skip) continue;
            const previous = previousRects.get(element);
            if (!previous) continue;
            const current = element.getBoundingClientRect();
            const dx = previous.left - current.left;
            const dy = previous.top - current.top;
            if (Math.abs(dx) < 1 && Math.abs(dy) < 1) continue;
            element.animate(
                [
                    { transform: `translate(${dx}px, ${dy}px)` },
                    { transform: "translate(0, 0)" },
                ],
                { duration, easing: "cubic-bezier(0.22, 1, 0.36, 1)" },
            );
        }
    });
}


export function animateVerticalFlip(
    previousRects,
    elements,
    {
        skip = null,
        duration = 380,
    } = {},
) {
    if (prefersReducedMotion()) return;

    requestAnimationFrame(() => {
        for (const element of elements) {
            if (element === skip) continue;

            const previous = previousRects.get(element);
            if (!previous) continue;

            const current = element.getBoundingClientRect();
            const dy = previous.top - current.top;

            if (Math.abs(dy) < 1) continue;

            element.animate(
                [
                    {
                        transform: `translateY(${dy}px)`,
                        opacity: 0.92,
                    },
                    {
                        transform: "translateY(0)",
                        opacity: 1,
                    },
                ],
                {
                    duration,
                    easing: "cubic-bezier(0.22, 1, 0.36, 1)",
                },
            );
        }
    });
}

export function animateEntrance(elements) {
    if (prefersReducedMotion()) return;
    elements.forEach((element, index) => {
        element.animate(
            [
                { opacity: 0, transform: "translateY(14px) scale(.985)" },
                { opacity: 1, transform: "translateY(0) scale(1)" },
            ],
            {
                duration: 520,
                delay: index * 42,
                easing: "cubic-bezier(0.22, 1, 0.36, 1)",
                fill: "both",
            },
        );
    });
}
