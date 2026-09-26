from app.contracts.action_plan import (
    ActionPlan,
    CreateTransactionAction,
    QueryFinancialDataAction,
)

from app.contracts.results import (
    PlanExecutionResult,
)


class MVPResponseFormatter:

    CONCEPTS_AR = {
        "charity": "الصدقات",
        "restaurants": "المطاعم",
        "restaurant": "المطاعم",
        "fuel": "الوقود",
        "books": "الكتب",
        "gifts": "الهدايا",
        "groceries": "البقالة",
        "coffee": "القهوة",
        "shopping": "التسوق",
        "subscriptions": "الاشتراكات",
    }

    def format(
        self,
        *,
        plan: ActionPlan,
        execution: PlanExecutionResult,
        user_message: str,
    ) -> str:

        if not execution.actions:
            return "تم تنفيذ الطلب."

        result_by_id = {
            result.action_id: result
            for result in execution.actions
        }

        responses = []

        for action in plan.actions:

            result = result_by_id.get(
                action.action_id
            )

            if result is None:
                continue

            # =============================
            # CREATE TRANSACTION
            # =============================

            if isinstance(
                action,
                CreateTransactionAction,
            ):
                data = result.data

                amount = self._money(
                    data["amount_minor"],
                    data["currency"],
                )

                merchant = data.get(
                    "merchant"
                )

                if merchant:
                    responses.append(
                        f"تم تسجيل {amount} "
                        f"في {merchant}."
                    )
                else:
                    responses.append(
                        f"تم تسجيل {amount}."
                    )

                continue

            # =============================
            # QUERY FINANCIAL DATA
            # =============================

            if isinstance(
                action,
                QueryFinancialDataAction,
            ):
                data = result.data

                metric = data.get(
                    "metric"
                )

                # =========================
                # BALANCE
                # =========================

                if metric == "balance":

                    amount = self._money(
                        data["amount_minor"],
                        data["currency"],
                    )

                    responses.append(
                        f"رصيدك الحالي هو {amount}."
                    )

                    continue

                # =========================
                # SPENDING
                # =========================

                if metric == "spending":

                    amount = self._money(
                        data["amount_minor"],
                        data["currency"],
                    )

                    concepts = (
                        action
                        .parameters
                        .filters
                        .concepts
                    )

                    period = self._period(
                        action
                    )

                    if concepts:

                        concept = self._concept(
                            concepts[0]
                        )

                        responses.append(
                            f"إجمالي إنفاقك على "
                            f"{concept} {period}: "
                            f"{amount}."
                        )

                    else:

                        responses.append(
                            f"إجمالي إنفاقك "
                            f"{period}: {amount}."
                        )

                    continue

        if responses:
            return "\n".join(
                responses
            )

        return "تم تنفيذ طلبك بنجاح."

    # =================================
    # HELPERS
    # =================================

    @staticmethod
    def _money(
        amount_minor: int,
        currency: str,
    ) -> str:

        amount = (
            amount_minor / 100
        )

        if amount.is_integer():
            number = (
                f"{int(amount):,}"
            )
        else:
            number = (
                f"{amount:,.2f}"
            )

        if currency.upper() == "SAR":
            return f"{number} ريال"

        return (
            f"{number} "
            f"{currency.upper()}"
        )

    def _concept(
        self,
        concept: str,
    ) -> str:

        normalized = (
            concept
            .strip()
            .lower()
        )

        return self.CONCEPTS_AR.get(
            normalized,
            concept,
        )

    @staticmethod
    def _period(
        action:
            QueryFinancialDataAction,
    ) -> str:

        period = (
            action.parameters.period
        )

        period_type = (
            period.type.value
        )

        if period_type == "calendar_day":

            if period.offset == 0:
                return "اليوم"

            if period.offset == -1:
                return "أمس"

        if period_type == "calendar_week":

            if period.offset == 0:
                return "هذا الأسبوع"

            if period.offset == -1:
                return "الأسبوع الماضي"

        if period_type == "calendar_month":

            if period.offset == 0:
                return "هذا الشهر"

            if period.offset == -1:
                return "الشهر الماضي"

        if period_type == "calendar_year":

            if period.offset == 0:
                return "هذه السنة"

            if period.offset == -1:
                return "السنة الماضية"

        return "خلال الفترة المحددة"