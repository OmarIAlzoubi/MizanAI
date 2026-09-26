import {
    fetchDashboard
} from "./api.js";


function moneyFromMinor(
    amountMinor
) {

    if (
        amountMinor === null
        || amountMinor === undefined
    ) {
        return "—";
    }

    const value =
        Number(
            amountMinor
        ) / 100;

    return (
        new Intl.NumberFormat(
            "en-US",
            {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            }
        )
        .format(
            value
        )
    );
}


function moneySignedFromMinor(
    amountMinor
) {

    const number =
        Number(
            amountMinor
        );

    const prefix =
        number > 0
        ? "+"
        : "";

    return (
        prefix
        + moneyFromMinor(
            amountMinor
        )
    );
}


function dateAr(
    value,
    options = {
        day: "numeric",
        month: "long"
    }
) {

    if (!value) {
        return "—";
    }

    const parts =
        String(
            value
        )
        .split("-")
        .map(
            Number
        );

    if (
        parts.length === 3
        && parts.every(
            Number.isFinite
        )
    ) {

        const [
            year,
            month,
            day
        ] = parts;

        const date =
            new Date(
                Date.UTC(
                    year,
                    month - 1,
                    day
                )
            );

        return (
            new Intl.DateTimeFormat(
                "ar-SA",
                {
                    ...options,
                    timeZone: "UTC"
                }
            )
            .format(
                date
            )
        );
    }

    return String(
        value
    );
}


function empty(
    element,
    message = "لا توجد بيانات كافية"
) {

    element.innerHTML = `
        <div class="empty-state">
            ${message}
        </div>
    `;
}


function renderTrend(
    daily
) {

    const container =
        document.getElementById(
            "spending-trend"
        );

    if (
        !Array.isArray(
            daily
        )
        || daily.length === 0
    ) {
        empty(
            container
        );

        return;
    }

    const values =
        daily.map(
            item =>
                Number(
                    item.amount_minor
                    ?? 0
                )
        );

    const width = 420;
    const height = 110;

    const left = 8;
    const right = 412;
    const top = 14;
    const bottom = 90;

    const maxValue =
        Math.max(
            ...values,
            1
        );

    const span =
        Math.max(
            daily.length - 1,
            1
        );

    const points =
        values.map(
            (
                value,
                index
            ) => {

                const x =
                    left
                    + (
                        (
                            right
                            - left
                        )
                        * index
                        / span
                    );

                const ratio =
                    value
                    / maxValue;

                const y =
                    bottom
                    - (
                        (
                            bottom
                            - top
                        )
                        * ratio
                    );

                return {
                    x,
                    y
                };
            }
        );

    const path =
        points
        .map(
            (
                point,
                index
            ) =>
                `${
                    index === 0
                    ? "M"
                    : "L"
                } ${point.x.toFixed(
                    2
                )} ${point.y.toFixed(
                    2
                )}`
        )
        .join(
            " "
        );

    const areaPath =
        `${path} `
        + `L ${right} ${bottom} `
        + `L ${left} ${bottom} Z`;

    const lastPoint =
        points[
            points.length - 1
        ];

    container.innerHTML = `
        <svg
            viewBox="0 0 ${width} ${height}"
            role="img"
            aria-label="اتجاه الإنفاق اليومي"
        >
            <line
                class="chart-gridline"
                x1="${left}"
                y1="${bottom}"
                x2="${right}"
                y2="${bottom}"
            />

            <line
                class="chart-gridline"
                x1="${left}"
                y1="50"
                x2="${right}"
                y2="50"
            />

            <path
                class="trend-area"
                d="${areaPath}"
            />

            <path
                class="trend-line"
                d="${path}"
            />

            <circle
                class="trend-dot"
                cx="${lastPoint.x}"
                cy="${lastPoint.y}"
                r="4"
            />
        </svg>
    `;
}


function renderConcepts(
    concepts
) {

    const container =
        document.getElementById(
            "concept-list"
        );

    if (
        !Array.isArray(
            concepts
        )
        || concepts.length === 0
    ) {

        empty(
            container,
            "لا توجد تصنيفات موثقة كافية لهذه الفترة"
        );

        return;
    }

    const top =
        concepts.slice(
            0,
            4
        );

    const maxValue =
        Math.max(
            ...top.map(
                item =>
                    Number(
                        item.amount_minor
                        ?? 0
                    )
            ),
            1
        );

    container.innerHTML =
        top.map(
            item => {

                const value =
                    Number(
                        item.amount_minor
                        ?? 0
                    );

                const width =
                    Math.max(
                        6,
                        (
                            value
                            / maxValue
                        )
                        * 100
                    );

                return `
                    <div class="concept-row">

                        <div class="concept-name">
                            ${
                                escapeHtml(
                                    item.concept
                                    ?? "غير مصنف"
                                )
                            }
                        </div>

                        <div class="concept-amount">
                            ${
                                moneyFromMinor(
                                    value
                                )
                            } ر.س
                        </div>

                        <div class="concept-track">
                            <div
                                class="concept-fill"
                                style="
                                    width:
                                        ${width}%;
                                "
                            ></div>
                        </div>

                    </div>
                `;
            }
        )
        .join(
            ""
        );
}


function renderMerchants(
    merchants
) {

    const container =
        document.getElementById(
            "merchant-list"
        );

    if (
        !Array.isArray(
            merchants
        )
        || merchants.length === 0
    ) {

        empty(
            container
        );

        return;
    }

    const top =
        merchants.slice(
            0,
            4
        );

    const maxValue =
        Math.max(
            ...top.map(
                item =>
                    Number(
                        item.amount_minor
                        ?? 0
                    )
            ),
            1
        );

    container.innerHTML =
        top.map(
            item => {

                const value =
                    Number(
                        item.amount_minor
                        ?? 0
                    );

                const width =
                    Math.max(
                        6,
                        (
                            value
                            / maxValue
                        )
                        * 100
                    );

                return `
                    <div class="merchant-row">

                        <div class="merchant-name">
                            ${
                                escapeHtml(
                                    item.merchant
                                    ?? "غير معروف"
                                )
                            }
                        </div>

                        <div class="merchant-amount">
                            ${
                                moneyFromMinor(
                                    value
                                )
                            } ر.س
                        </div>

                        <div class="merchant-track">
                            <div
                                class="merchant-fill"
                                style="
                                    width:
                                        ${width}%;
                                "
                            ></div>
                        </div>

                    </div>
                `;
            }
        )
        .join(
            ""
        );
}


function renderDaily(
    daily
) {

    const container =
        document.getElementById(
            "daily-bars"
        );

    if (
        !Array.isArray(
            daily
        )
        || daily.length === 0
    ) {

        empty(
            container
        );

        return;
    }

    const values =
        daily.map(
            item =>
                Number(
                    item.amount_minor
                    ?? 0
                )
        );

    const maxValue =
        Math.max(
            ...values,
            1
        );

    const maxIndex =
        values.indexOf(
            Math.max(
                ...values
            )
        );

    const highest =
        daily[
            maxIndex
        ];

    document
        .getElementById(
            "daily-highest"
        )
        .innerHTML =
            `${
                moneyFromMinor(
                    highest.amount_minor
                )
            } <small>ر.س</small>`;

    document
        .getElementById(
            "daily-highest-note"
        )
        .textContent =
            `أعلى يوم: ${
                dateAr(
                    highest.date,
                    {
                        day: "numeric",
                        month: "short"
                    }
                )
            }`;

    container.innerHTML =
        daily.map(
            item => {

                const value =
                    Number(
                        item.amount_minor
                        ?? 0
                    );

                const height =
                    Math.max(
                        4,
                        (
                            value
                            / maxValue
                        )
                        * 100
                    );

                const day =
                    dateAr(
                        item.date,
                        {
                            day: "numeric"
                        }
                    );

                return `
                    <div class="daily-column">

                        <div
                            class="daily-bar"
                            title="${
                                moneyFromMinor(
                                    value
                                )
                            } ر.س"
                            style="
                                height:
                                    ${height}%;
                            "
                        ></div>

                        <div class="daily-label">
                            ${day}
                        </div>

                    </div>
                `;
            }
        )
        .join(
            ""
        );
}


function renderPeriod(
    period
) {

    if (
        !period
        || !period.start_date
        || !period.end_date
    ) {
        return "—";
    }

    const start =
        dateAr(
            period.start_date,
            {
                day: "numeric",
                month: "short"
            }
        );

    const end =
        dateAr(
            period.end_date,
            {
                day: "numeric",
                month: "short"
            }
        );

    if (
        period.start_date
        === period.end_date
    ) {
        return start;
    }

    return (
        `${start} – ${end}`
    );
}


function escapeHtml(
    value
) {

    return (
        String(
            value
        )
        .replaceAll(
            "&",
            "&amp;"
        )
        .replaceAll(
            "<",
            "&lt;"
        )
        .replaceAll(
            ">",
            "&gt;"
        )
        .replaceAll(
            "\"",
            "&quot;"
        )
        .replaceAll(
            "'",
            "&#039;"
        )
    );
}


function renderMonthlyComparison(
    items
) {

    const container =
        document.getElementById(
            "monthly-comparison-chart"
        );

    if (
        !container
        || !Array.isArray(items)
        || items.length === 0
    ) {
        if (container) {
            empty(
                container,
                "لا توجد أشهر كافية للمقارنة"
            );
        }

        return;
    }

    const maxValue =
        Math.max(
            ...items.map(
                item =>
                    Number(
                        item.amount_minor
                        ?? 0
                    )
            ),
            1
        );

    const currentMonth =
        items[
            items.length - 1
        ]?.month;

    container.innerHTML =
        items.map(
            item => {

                const value =
                    Number(
                        item.amount_minor
                        ?? 0
                    );

                const height =
                    Math.max(
                        5,
                        value / maxValue * 100
                    );

                const monthDate =
                    `${item.month}-01`;

                const label =
                    dateAr(
                        monthDate,
                        {
                            month: "short"
                        }
                    );

                return `
                    <div class="month-column ${
                        item.month === currentMonth
                        ? "is-current"
                        : ""
                    }">

                        <div class="month-bar-wrap">
                            <div
                                class="month-bar"
                                style="height:${height}%"
                            ></div>
                        </div>

                        <div class="month-amount">
                            ${moneyFromMinor(value)} ر.س
                        </div>

                        <div class="month-label">
                            ${label}
                        </div>

                    </div>
                `;
            }
        )
        .join("");
}


function renderConceptWidget(
    prefix,
    data
) {

    const amount =
        document.getElementById(
            `${prefix}-amount`
        );

    if (!amount) {
        return;
    }

    amount.innerHTML =
        `${moneyFromMinor(
            data?.amount_minor
            ?? 0
        )} <small>ر.س</small>`;

    const count =
        document.getElementById(
            `${prefix}-count`
        );

    if (count) {
        count.textContent =
            `${Number(
                data?.transaction_count
                ?? 0
            )}`;
    }

    const average =
        document.getElementById(
            `${prefix}-average`
        );

    if (average) {
        average.textContent =
            `${moneyFromMinor(
                data?.average_transaction_minor
                ?? 0
            )} ر.س`;
    }
}


function renderBnpl(
    data,
    spending
) {

    renderConceptWidget(
        "bnpl",
        data
    );


    const count =
        Number(
            data?.transaction_count
            ?? 0
        );


    const average =
        Number(
            data?.average_transaction_minor
            ?? 0
        );


    const amount =
        Number(
            data?.amount_minor
            ?? 0
        );


    const totalSpending =
        Number(
            spending?.amount_minor
            ?? 0
        );


    const sharePercent =
        totalSpending > 0
        ? (
            amount
            / totalSpending
        ) * 100
        : 0;


    const meta =
        document.getElementById(
            "bnpl-meta"
        );


    if (meta) {

        meta.textContent =
            `${count} دفعات · متوسط ${
                moneyFromMinor(
                    average
                )
            } ر.س`;
    }


    const share =
        document.getElementById(
            "bnpl-share"
        );


    if (share) {

        share.textContent =
            `${sharePercent.toFixed(
                1
            )}% من مصروف الشهر`;
    }


    const providers =
        document.getElementById(
            "bnpl-providers"
        );


    if (!providers) {
        return;
    }


    const merchants =
        data?.top_merchants
        ?? [];


    if (
        !Array.isArray(
            merchants
        )
        || merchants.length === 0
    ) {

        providers.innerHTML = `
            <div class="empty-state">
                لا توجد مدفوعات تقسيط
            </div>
        `;

        return;
    }


    providers.innerHTML =
        merchants.map(
            item => {

                const providerAmount =
                    Number(
                        item.amount_minor
                        ?? 0
                    );


                const providerPercent =
                    amount > 0
                    ? (
                        providerAmount
                        / amount
                    ) * 100
                    : 0;


                return `
                    <div class="bnpl-provider">

                        <div class="bnpl-provider-head">

                            <div class="bnpl-provider-title">

                                <strong>
                                    ${escapeHtml(
                                        item.merchant
                                        ?? "غير معروف"
                                    )}
                                </strong>

                                <span>
                                    ${providerPercent.toFixed(
                                        1
                                    )}%
                                </span>

                            </div>


                            <span class="bnpl-provider-amount">
                                ${moneyFromMinor(
                                    providerAmount
                                )} ر.س
                            </span>

                        </div>


                        <div class="bnpl-provider-track">

                            <div
                                class="bnpl-provider-fill"
                                style="
                                    width:
                                        ${providerPercent}%;
                                "
                            ></div>

                        </div>

                    </div>
                `;
            }
        )
        .join("");
}


function renderCoffee(
    data
) {

    renderConceptWidget(
        "coffee",
        data
    );

    const top =
        document.getElementById(
            "coffee-top-merchant"
        );

    if (!top) {
        return;
    }

    const merchant =
        data?.top_merchants?.[0];

    top.textContent =
        merchant
        ? `أعلى جهة: ${
            merchant.merchant
            ?? "غير معروف"
        } · ${
            moneyFromMinor(
                merchant.amount_minor
                ?? 0
            )
        } ر.س`
        : "لا توجد عمليات قهوة موثقة";
}


function renderLargestTransactions(
    items
) {

    const container =
        document.getElementById(
            "largest-transactions-list"
        );

    if (!container) {
        return;
    }

    if (
        !Array.isArray(items)
        || items.length === 0
    ) {
        empty(
            container,
            "لا توجد عمليات إنفاق في هذه الفترة"
        );

        return;
    }

    container.innerHTML =
        items.map(
            item => `
                <div class="largest-row">

                    <div class="largest-merchant">
                        ${escapeHtml(
                            item.merchant
                            ?? "غير معروف"
                        )}
                    </div>

                    <div class="largest-amount">
                        ${moneyFromMinor(
                            item.amount_minor
                            ?? 0
                        )} ر.س
                    </div>

                    <div class="largest-date">
                        ${dateAr(
                            item.local_date,
                            {
                                day: "numeric",
                                month: "short"
                            }
                        )}
                    </div>

                </div>
            `
        )
        .join("");
}


export async function initDashboard() {

    const updated =
        document.getElementById(
            "last-update"
        );

    try {

        const data =
            await fetchDashboard();

        const balance =
            data.balance
            ?? {};

        const spending =
            data.spending
            ?? {};

        const period =
            data.period
            ?? {};

        const cashFlow =
            data.cash_flow
            ?? {};


        document
            .getElementById(
                "balance-number"
            )
            .textContent =
                moneyFromMinor(
                    balance.amount_minor
                );


        document
            .getElementById(
                "balance-currency"
            )
            .textContent =
                balance.currency
                === "SAR"
                ? "ر.س"
                : (
                    balance.currency
                    ?? "ر.س"
                );


        updated.textContent =
            period.coverage_end_date
            ? `آخر بيانات متاحة: ${
                dateAr(
                    period
                    .coverage_end_date
                )
            }`
            : "لا توجد بيانات مالية بعد";


        const periodText =
            renderPeriod(
                period
            );

        [
            "spending-period",
            "merchants-period",
            "cashflow-period"
        ]
        .forEach(
            id => {

                document
                    .getElementById(
                        id
                    )
                    .textContent =
                        periodText;
            }
        );


        const spendingAmountElement =
            document.getElementById(
                "spending-amount"
            )
            ?? document.getElementById(
                "month-spending"
            );


        if (spendingAmountElement) {

            spendingAmountElement.innerHTML =
                `${
                    moneyFromMinor(
                        spending
                        .amount_minor
                    )
                } <small>ر.س</small>`;
        }


        const delta =
            Number(
                spending
                .delta_minor
                ?? 0
            );


        const spendingComparison =
            document.getElementById(
                "spending-comparison"
            );


        if (spendingComparison) {

            if (delta === 0) {

                spendingComparison.textContent =
                    "مساوٍ لنفس المدة في الشهر السابق";

            }

            else {

                spendingComparison.textContent =
                    `${
                        delta > 0
                        ? "أعلى"
                        : "أقل"
                    } من نفس المدة في الشهر السابق بـ ${
                        moneyFromMinor(
                            Math.abs(
                                delta
                            )
                        )
                    } ر.س`;
            }
        }


        const spendingDaysCount =
            Array.isArray(
                spending.daily
            )
            ? spending.daily.length
            : 0;


        const spendingDailyAverage =
            spendingDaysCount > 0
            ? Math.round(
                Number(
                    spending.amount_minor
                    ?? 0
                )
                / spendingDaysCount
            )
            : 0;


        const spendingDailyAverageElement =
            document.getElementById(
                "spending-daily-average"
            );


        if (spendingDailyAverageElement) {

            spendingDailyAverageElement.textContent =
                `متوسط يومي ${
                    moneyFromMinor(
                        spendingDailyAverage
                    )
                } ر.س`;
        }


        const spendingTransactionsElement =
            document.getElementById(
                "spending-transactions"
            );


        if (spendingTransactionsElement) {

            spendingTransactionsElement.textContent =
                `${
                    Number(
                        spending.transaction_count
                        ?? 0
                    )
                } عملية`;
        }


        document
            .getElementById(
                "transaction-count"
            )
            .textContent =
                String(
                    spending
                    .transaction_count
                    ?? 0
                );


        document
            .getElementById(
                "average-transaction"
            )
            .textContent =
                `${
                    moneyFromMinor(
                        spending
                        .average_transaction_minor
                    )
                } ر.س`;


        document
            .getElementById(
                "largest-transaction"
            )
            .textContent =
                `${
                    moneyFromMinor(
                        spending
                        .largest_transaction_minor
                    )
                } ر.س`;


        document
            .getElementById(
                "coverage-day"
            )
            .textContent =
                period.coverage_end_date
                ? dateAr(
                    period
                    .coverage_end_date,
                    {
                        day: "numeric",
                        month: "short"
                    }
                )
                : "—";


        document
            .getElementById(
                "cash-in"
            )
            .textContent =
                `${
                    moneyFromMinor(
                        cashFlow
                        .inflow_minor
                    )
                } ر.س`;


        document
            .getElementById(
                "cash-out"
            )
            .textContent =
                `${
                    moneyFromMinor(
                        cashFlow
                        .outflow_minor
                    )
                } ر.س`;


        const net =
            Number(
                cashFlow
                .net_minor
                ?? 0
            );

        document
            .getElementById(
                "cash-net"
            )
            .textContent =
                `صافي الحركة: ${
                    moneySignedFromMinor(
                        net
                    )
                } ر.س`;


        renderTrend(
            spending.daily
            ?? []
        );

        renderDaily(
            data.last_7_days
            ?? []
        );

        renderMerchants(
            data.top_merchants
            ?? []
        );

        renderConcepts(
            data.top_concepts
            ?? []
        );

        renderMonthlyComparison(
            data.monthly_comparison
            ?? []
        );

        renderBnpl(
            data.bnpl
            ?? {},

            data.spending
            ?? {}
        );

        renderCoffee(
            data.coffee
            ?? {}
        );

        renderLargestTransactions(
            data.largest_transactions
            ?? []
        );

    }

    catch (error) {

        updated.textContent =
            "تعذر تحميل بيانات لوحة المعلومات";

        console.error(
            "[Dashboard]",
            error
        );
    }
}
