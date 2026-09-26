from __future__ import annotations

import os
import random
import re

from dataclasses import dataclass
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from app.core.config import (
    get_settings,
)
from app.infrastructure.database.connection import (
    Database,
    get_default_database,
)


load_dotenv()


@dataclass(frozen=True)
class FriendlyReply:
    intent: str
    reply: str
    used_financial_nudge: bool = False


class FriendlyConversationService:
    """
    Fast deterministic path for pure social messages.

    Important:
    - It only captures clearly social messages.
    - Financial questions continue through the normal Mizan pipeline.
    - Optional financial nudges are based on verified database values.
    """

    NUDGE_PROBABILITY = 0.25
    NUDGE_COOLDOWN = timedelta(
        hours=6
    )

    _ARABIC_DIACRITICS = re.compile(
        r"[\u0617-\u061A\u064B-\u0652\u0670\u06D6-\u06ED]"
    )

    _PUNCTUATION = re.compile(
        r"""[^\w\s\u0600-\u06FF]+""",
        re.UNICODE,
    )

    SALAM = {
        "السلام عليكم",
        "سلام عليكم",
        "السلام عليكم ورحمة الله",
        "السلام عليكم ورحمه الله",
    }

    GREETING = {
        "مرحبا",
        "اهلا",
        "اهلين",
        "هلا",
        "هلا والله",
        "يا هلا",
        "صباح الخير",
        "مساء الخير",
        "هاي",
        "hello",
        "hi",
        "hey",
        "مرحبا كيف حالك",
        "اهلا كيف حالك",
        "هلا كيفك",
    }

    HOW_ARE_YOU = {
        "كيف حالك",
        "كيفك",
        "شلونك",
        "وش اخبارك",
        "وش اخبارك اليوم",
        "كيف امورك",
        "كيف الامور",
        "how are you",
    }

    THANKS = {
        "شكرا",
        "شكرا لك",
        "مشكور",
        "يعطيك العافيه",
        "يعطيك العافية",
        "تسلم",
        "thanks",
        "thank you",
    }

    IDENTITY = {
        "من انت",
        "مين انت",
        "عرفني بنفسك",
        "عرف عن نفسك",
        "ايش انت",
        "وش انت",
        "من تكون",
        "who are you",
    }

    GOODBYE = {
        "مع السلامه",
        "مع السلامة",
        "باي",
        "تصبح على خير",
        "اشوفك بعدين",
        "نشوفك بعدين",
        "bye",
        "goodbye",
    }

    def __init__(
        self,
        *,
        database: Database | None = None,
        rng=None,
    ):
        self.database = (
            database
            or get_default_database()
        )

        self.settings = (
            get_settings()
        )

        self.rng = (
            rng
            or random.SystemRandom()
        )

        self._last_nudge_at: (
            datetime | None
        ) = None

    # =====================================================
    # PUBLIC API
    # =====================================================

    def try_reply(
        self,
        message: str,
    ) -> FriendlyReply | None:

        intent = self._detect_intent(
            message
        )

        if intent is None:
            return None

        name = self._user_name()

        base_reply = self._base_reply(
            intent=intent,
            name=name,
        )

        if (
            intent
            in {
                "salam",
                "greeting",
            }
            and self._should_try_nudge()
        ):
            nudge = (
                self._verified_spending_nudge()
            )

            if nudge:
                self._last_nudge_at = (
                    datetime.now(
                        timezone.utc
                    )
                )

                return FriendlyReply(
                    intent=intent,
                    reply=self._join_reply(
                        base_reply,
                        nudge,
                    ),
                    used_financial_nudge=True,
                )

        return FriendlyReply(
            intent=intent,
            reply=base_reply,
            used_financial_nudge=False,
        )

    # =====================================================
    # INTENT
    # =====================================================

    def _detect_intent(
        self,
        message: str,
    ) -> str | None:

        normalized = self._normalize(
            message
        )

        if not normalized:
            return None

        if normalized in self.SALAM:
            return "salam"

        if normalized in self.GREETING:
            return "greeting"

        if normalized in self.HOW_ARE_YOU:
            return "how_are_you"

        if normalized in self.THANKS:
            return "thanks"

        if normalized in self.IDENTITY:
            return "identity"

        if normalized in self.GOODBYE:
            return "goodbye"

        return None

    @classmethod
    def _normalize(
        cls,
        text: str,
    ) -> str:

        value = (
            text
            .strip()
            .lower()
            .replace("ـ", "")
        )

        value = (
            cls._ARABIC_DIACRITICS
            .sub(
                "",
                value,
            )
        )

        value = (
            value
            .replace("أ", "ا")
            .replace("إ", "ا")
            .replace("آ", "ا")
            .replace("ؤ", "و")
            .replace("ئ", "ي")
            .replace("ى", "ي")
        )

        value = (
            cls._PUNCTUATION
            .sub(
                " ",
                value,
            )
        )

        return " ".join(
            value.split()
        )

    # =====================================================
    # PERSONALITY
    # =====================================================

    def _base_reply(
        self,
        *,
        intent: str,
        name: str | None,
    ) -> str:

        named = (
            f" يا {name}"
            if name
            else ""
        )

        if intent == "salam":
            choices = [
                (
                    "وعليكم السلام"
                    f"{named} 👋 "
                    "وش حاب تعرف اليوم؟"
                ),
                (
                    "وعليكم السلام ورحمة الله"
                    f"{named} 👋 "
                    "كيف أقدر أفيدك؟"
                ),
                (
                    "وعليكم السلام"
                    f"{named} 🤝 "
                    "وش نراجع اليوم؟"
                ),
            ]

        elif intent == "greeting":
            choices = [
                (
                    f"هلا{named} 👋 "
                    "كيف أقدر أفيدك اليوم؟"
                ),
                (
                    f"يا هلا{named} 😄 "
                    "وش حاب تعرف؟"
                ),
                (
                    f"أهلين{named} 👋 "
                    "وش نراجع اليوم؟"
                ),
            ]

        elif intent == "how_are_you":
            choices = [
                (
                    "بخير دام أمورك بخير 😄 "
                    "وش حاب نراجع اليوم؟"
                ),
                (
                    "تمام الحمدلله 👌 "
                    "وأنت كيفك؟"
                ),
                (
                    "تمام 😄 جاهز نحسبها "
                    "ونفهمها سوا."
                ),
            ]

        elif intent == "thanks":
            choices = [
                (
                    f"العفو{named} 🤝 "
                    "بأي وقت."
                ),
                (
                    "حياك 😄 هذا شغلي."
                ),
                (
                    "ولو 👌 إذا احتجت أي "
                    "شيء مالي أنا موجود."
                ),
            ]

        elif intent == "identity":
            choices = [
                (
                    "أنا MizanAI، مساعدك المالي الشخصي. "
                    "أقدر أفهم كلامك الطبيعي، أسجل مصاريفك، "
                    "أحلل نمط صرفك، وأجاوبك عن بياناتك المالية "
                    "مع الاعتماد على الأرقام الفعلية بدل التخمين."
                ),
                (
                    "أنا MizanAI 👋 مساعد مالي شخصي يساعدك "
                    "تتابع فلوسك وتفهم وين يروح صرفك. "
                    "أستخدم الذكاء الاصطناعي لفهم سؤالك، "
                    "لكن الحسابات والحقائق المالية آخذها "
                    "من بياناتك الفعلية."
                ),
            ]

        elif intent == "goodbye":
            choices = [
                (
                    f"في أمان الله{named} 👋"
                ),
                (
                    "نشوفك على خير 👋"
                ),
                (
                    "مع السلامة 🤝"
                ),
            ]

        else:
            choices = [
                "هلا 👋 كيف أقدر أفيدك؟"
            ]

        return self.rng.choice(
            choices
        )

    # =====================================================
    # VERIFIED FINANCIAL NUDGE
    # =====================================================

    def _should_try_nudge(
        self,
    ) -> bool:

        now = datetime.now(
            timezone.utc
        )

        if (
            self._last_nudge_at
            is not None
            and (
                now
                - self._last_nudge_at
            )
            < self.NUDGE_COOLDOWN
        ):
            return False

        return (
            self.rng.random()
            < self.NUDGE_PROBABILITY
        )

    def _verified_spending_nudge(
        self,
    ) -> str | None:

        try:
            values = (
                self._yesterday_vs_baseline()
            )
        except Exception as exc:
            # Friendly conversation must never
            # fail because an optional insight failed.
            print(
                "[Friendly Conversation] "
                "Nudge unavailable:"
            )
            print(
                f"{type(exc).__name__}: "
                f"{exc}"
            )
            return None

        if values is None:
            return None

        (
            yesterday_minor,
            baseline_daily_minor,
        ) = values

        # We only say "higher than usual" when
        # there is a meaningful baseline.
        if baseline_daily_minor <= 0:
            return None

        difference_minor = (
            yesterday_minor
            - baseline_daily_minor
        )

        ratio = (
            yesterday_minor
            / baseline_daily_minor
        )

        # Avoid surfacing tiny or noisy changes.
        is_meaningfully_high = (
            yesterday_minor
            >= 10_000
            and difference_minor
            >= 5_000
            and ratio
            >= 1.40
        )

        if not is_meaningfully_high:
            return None

        choices = [
            (
                "بالمناسبة، صرفك أمس كان "
                "أعلى من متوسط الأيام السبعة "
                "اللي قبله بشكل واضح 😄 "
                "تحب أشوف لك وين راح أغلبه؟"
            ),
            (
                "على طاري الفلوس 👀 أمس كان "
                "صرفك أعلى من المعتاد شوي. "
                "تحب أعطيك ملخص سريع؟"
            ),
            (
                "أمس كان يوم صرف ثقيل شوي 😄 "
                "انبسطت؟ إذا تحب أقدر أوضح لك "
                "وين راح أغلب الصرف."
            ),
        ]

        return self.rng.choice(
            choices
        )

    def _yesterday_vs_baseline(
        self,
    ) -> tuple[int, float] | None:

        tz = ZoneInfo(
            self.settings.default_timezone
        )

        now_local = datetime.now(
            tz
        )

        today_start_local = (
            now_local
            .replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
        )

        yesterday_start_local = (
            today_start_local
            - timedelta(days=1)
        )

        baseline_start_local = (
            yesterday_start_local
            - timedelta(days=7)
        )

        yesterday_start_utc = (
            yesterday_start_local
            .astimezone(
                timezone.utc
            )
        )

        today_start_utc = (
            today_start_local
            .astimezone(
                timezone.utc
            )
        )

        baseline_start_utc = (
            baseline_start_local
            .astimezone(
                timezone.utc
            )
        )

        with self.database.session() as conn:

            row = conn.execute(
                """
                SELECT
                    COALESCE(
                        SUM(
                            CASE
                                WHEN
                                    occurred_at_utc >= ?
                                    AND occurred_at_utc < ?
                                THEN amount_minor
                                ELSE 0
                            END
                        ),
                        0
                    ) AS yesterday_minor,

                    COALESCE(
                        SUM(
                            CASE
                                WHEN
                                    occurred_at_utc >= ?
                                    AND occurred_at_utc < ?
                                THEN amount_minor
                                ELSE 0
                            END
                        ),
                        0
                    ) AS baseline_minor

                FROM v_financial_transactions

                WHERE
                    status = 'posted'
                    AND direction = 'debit'
                    AND financial_nature = 'expense'
                """,
                (
                    yesterday_start_utc.isoformat(),
                    today_start_utc.isoformat(),
                    baseline_start_utc.isoformat(),
                    yesterday_start_utc.isoformat(),
                ),
            ).fetchone()

        if row is None:
            return None

        yesterday_minor = int(
            row["yesterday_minor"]
            or 0
        )

        baseline_minor = int(
            row["baseline_minor"]
            or 0
        )

        if yesterday_minor <= 0:
            return None

        baseline_daily_minor = (
            baseline_minor
            / 7.0
        )

        return (
            yesterday_minor,
            baseline_daily_minor,
        )

    # =====================================================
    # HELPERS
    # =====================================================

    @staticmethod
    def _join_reply(
        base: str,
        nudge: str,
    ) -> str:

        return (
            f"{base}\n\n{nudge}"
        )

    @staticmethod
    def _user_name() -> str | None:
        """
        Keep personalization local/configurable.

        Example in local .env:
            MIZAN_USER_NAME=Omar
        """

        value = (
            os.getenv(
                "MIZAN_USER_NAME",
                ""
            )
            .strip()
        )

        return (
            value
            if value
            else None
        )
