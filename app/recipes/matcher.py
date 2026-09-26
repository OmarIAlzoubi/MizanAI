import re
import unicodedata

from dataclasses import dataclass

from app.recipes.repository import (
    RecipeRepository,
)


# =========================================================
# RESULT
# =========================================================


@dataclass(frozen=True)
class RecipeMatch:

    recipe_id: str

    name: str

    objective: str

    recipe: dict

    score: float

    matched_example: str


# =========================================================
# ARABIC NORMALIZATION
# =========================================================


_ARABIC_DIACRITICS = re.compile(
    r"[\u0617-\u061A"
    r"\u064B-\u0652"
    r"\u0670"
    r"\u06D6-\u06ED]"
)


# =========================================================
# TEMPORAL MASKING
# =========================================================


_PERIOD_PATTERNS = [

    # Arabic
    r"\bهذا الشهر\b",
    r"\bهالشهر\b",
    r"\bالشهر الحالي\b",
    r"\bالشهر الماضي\b",
    r"\bالشهر السابق\b",

    r"\bهذا الاسبوع\b",
    r"\bهالاسبوع\b",
    r"\bالاسبوع الحالي\b",
    r"\bالاسبوع الماضي\b",
    r"\bالاسبوع السابق\b",

    r"\bاليوم\b",
    r"\bامس\b",
    r"\bقبل امس\b",

    r"\bاخر\s+\d+\s+ايام\b",
    r"\bاخر\s+\d+\s+اسابيع\b",
    r"\bاخر\s+\d+\s+شهور\b",
    r"\bاخر\s+\d+\s+اشهر\b",

    # English
    r"\bthis month\b",
    r"\blast month\b",
    r"\bcurrent month\b",

    r"\bthis week\b",
    r"\blast week\b",

    r"\btoday\b",
    r"\byesterday\b",

    r"\blast\s+\d+\s+days\b",
    r"\blast\s+\d+\s+weeks\b",
    r"\blast\s+\d+\s+months\b",
]


# =========================================================
# LIGHTWEIGHT CANONICAL VOCABULARY
# =========================================================


_TOKEN_ALIASES = {

    # -------------------------
    # WHY / EXPLANATION
    # -------------------------

    "ليش": "why",
    "لماذا": "why",
    "سبب": "why",
    "السبب": "why",
    "اسباب": "why",

    # -------------------------
    # SPENDING
    # -------------------------

    "صرفي": "spending",
    "صرف": "spending",
    "الصرف": "spending",

    "مصاريفي": "spending",
    "مصاريف": "spending",
    "المصاريف": "spending",

    "مصروفي": "spending",
    "مصروفاتي": "spending",

    "انفاقي": "spending",
    "الانفاق": "spending",
    "انفاق": "spending",

    # -------------------------
    # INCREASE
    # -------------------------


    "رفع": "increase",
    "رفعت": "increase",
    "يرفع": "increase",
    "رافع": "increase",
    "رفعتلي": "increase",
    "مرتفع": "increase",
    "مرتفعه": "increase",
    "عالي": "increase",
    "عاليه": "increase",

    "زاد": "increase",
    "زادت": "increase",
    "زايد": "increase",

    "زيادة": "increase",
    "الزيادة": "increase",

    "ارتفع": "increase",
    "ارتفعت": "increase",
    "ارتفاع": "increase",

    # -------------------------
    # DECREASE
    # -------------------------

    "انخفض": "decrease",
    "انخفضت": "decrease",
    "انخفاض": "decrease",

    "قل": "decrease",
    "قلت": "decrease",
    "اقل": "decrease",

    # -------------------------
    # COMPARE
    # -------------------------

    "قارن": "compare",
    "مقارنة": "compare",
    "الفرق": "compare",

    # -------------------------
    # TREND
    # -------------------------

    "اتجاه": "trend",
    "نمط": "trend",
    "تغير": "trend",
    "تغيرت": "trend",

    # -------------------------
    # ENGLISH
    # -------------------------

    "expenses": "spending",
    "expense": "spending",
    "spend": "spending",
    "spending": "spending",

    "higher": "increase",
    "high": "increase",
    "increased": "increase",
    "increase": "increase",

    "why": "why",
    "reason": "why",
    "reasons": "why",

    "compare": "compare",
    "difference": "compare",

    "trend": "trend",
}


_STOPWORDS = {

    # Arabic

    "اللي",
    "الي",
    "إيش",
    "ايش",
    "انا",
    "عندي",
    "عند",
    "في",
    "من",
    "على",
    "عن",
    "الى",
    "الي",
    "هو",
    "هي",
    "كان",
    "كانت",
    "صار",
    "صارت",
    "وش",
    "ايش",
    "ما",
    "هل",

    # English
    "i",
    "my",
    "me",
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "in",
    "on",
    "of",
    "for",
    "to",
}


# =========================================================
# NORMALIZER
# =========================================================


def normalize_recipe_text(
    text: str,
) -> str:

    if not text:
        return ""

    text = unicodedata.normalize(
        "NFKC",
        text,
    )

    text = text.casefold()

    # Remove Arabic diacritics
    text = (
        _ARABIC_DIACRITICS
        .sub(
            "",
            text,
        )
    )

    # Remove tatweel
    text = text.replace(
        "ـ",
        "",
    )

    # Arabic letter normalization
    text = re.sub(
        r"[أإآٱ]",
        "ا",
        text,
    )

    text = text.replace(
        "ى",
        "ي",
    )

    text = text.replace(
        "ؤ",
        "و",
    )

    text = text.replace(
        "ئ",
        "ي",
    )

    # -----------------------------------------
    # Replace temporal expressions
    # -----------------------------------------

    for pattern in _PERIOD_PATTERNS:

        text = re.sub(
            pattern,
            " period ",
            text,
            flags=re.IGNORECASE,
        )

    # -----------------------------------------
    # Numbers become generic parameters
    # -----------------------------------------

    text = re.sub(
        r"\b\d+(?:[.,]\d+)?\b",
        " num ",
        text,
    )

    # -----------------------------------------
    # Remove punctuation
    # -----------------------------------------

    text = re.sub(
        r"[^\w\s]",
        " ",
        text,
        flags=re.UNICODE,
    )

    tokens = []

    for raw_token in text.split():

        token = raw_token.strip()

        if not token:
            continue

        if token in _STOPWORDS:
            continue

        token = (
            _TOKEN_ALIASES
            .get(
                token,
                token,
            )
        )

        tokens.append(
            token
        )

    return " ".join(
        tokens
    )


# =========================================================
# SIMILARITY
# =========================================================


def _token_f1(
    a: str,
    b: str,
) -> float:

    set_a = set(
        a.split()
    )

    set_b = set(
        b.split()
    )

    if (
        not set_a
        or not set_b
    ):
        return 0.0

    overlap = len(
        set_a
        & set_b
    )

    # Require at least two meaningful
    # shared concepts.
    if overlap < 2:
        return 0.0

    precision = (
        overlap
        / len(set_a)
    )

    recall = (
        overlap
        / len(set_b)
    )

    denominator = (
        precision
        + recall
    )

    if denominator == 0:
        return 0.0

    return (
        2
        * precision
        * recall
        / denominator
    )


def _char_ngrams(
    text: str,
    n: int = 3,
) -> set[str]:

    compact = re.sub(
        r"\s+",
        " ",
        text.strip(),
    )

    if not compact:
        return set()

    if len(compact) <= n:

        return {
            compact
        }

    return {
        compact[index:index + n]

        for index in range(
            len(compact) - n + 1
        )
    }


def _dice_similarity(
    a: str,
    b: str,
) -> float:

    grams_a = (
        _char_ngrams(a)
    )

    grams_b = (
        _char_ngrams(b)
    )

    if (
        not grams_a
        or not grams_b
    ):
        return 0.0

    overlap = len(
        grams_a
        & grams_b
    )

    return (
        2.0
        * overlap
        / (
            len(grams_a)
            + len(grams_b)
        )
    )


def recipe_similarity(
    query: str,
    example: str,
) -> float:

    query_tokens = set(
        query.split()
    )

    example_tokens = set(
        example.split()
    )

    if (
        not query_tokens
        or not example_tokens
    ):
        return 0.0

    overlap = len(
        query_tokens
        & example_tokens
    )

    # A single shared word is too weak.
    #
    # Example:
    # "spending"
    # should never be enough to activate
    # an analytical recipe.
    if overlap < 2:
        return 0.0

    token_score = (
        _token_f1(
            query,
            example,
        )
    )

    # =====================================================
    # QUERY COVERAGE
    # =====================================================
    #
    # Short natural-language requests are common:
    #
    # "ايش رفع مصاريفي؟"
    #
    # may normalize to:
    #
    # "increase spending"
    #
    # while the stored recipe example could be:
    #
    # "why spending increase period"
    #
    # F1 alone unfairly penalizes the shorter query,
    # even though every meaningful query token matches.
    # =====================================================

    query_coverage = (
        overlap
        / len(query_tokens)
    )

    semantic_score = (
        token_score
    )

    # Strong containment bonus only for short,
    # focused queries where ALL meaningful
    # query tokens are represented in the example.
    if (
        len(query_tokens) <= 3
        and query_coverage == 1.0
    ):

        semantic_score = max(
            semantic_score,
            0.92,
        )

    else:

        # For longer queries, coverage still matters,
        # but F1 remains the primary signal.
        semantic_score = (
            0.80 * token_score
            + 0.20 * query_coverage
        )

    char_score = (
        _dice_similarity(
            query,
            example,
        )
    )

    final_score = (
        0.88 * semantic_score
        + 0.12 * char_score
    )

    return min(
        final_score,
        1.0,
    )

# =========================================================
# MATCHER
# =========================================================


class RecipeMatcher:

    DEFAULT_THRESHOLD = 0.78

    DEFAULT_MIN_MARGIN = 0.06

    def __init__(
        self,
        repository:
            RecipeRepository | None = None,
        threshold: float = DEFAULT_THRESHOLD,
        min_margin: float = DEFAULT_MIN_MARGIN,
    ):

        self.repository = (
            repository
            or RecipeRepository()
        )

        self.threshold = threshold

        self.min_margin = (
            min_margin
        )

    # =====================================================
    # MATCH
    # =====================================================

    def match(
        self,
        text: str,
    ) -> RecipeMatch | None:

        normalized_query = (
            normalize_recipe_text(
                text
            )
        )

        if not normalized_query:
            return None

        recipes = (
            self.repository
            .list_active()
        )

        scored_matches = []

        for recipe in recipes:

            best_score = 0.0

            best_example = None

            for example in (
                recipe["examples"]
            ):

                score = (
                    recipe_similarity(
                        normalized_query,
                        example[
                            "normalized"
                        ],
                    )
                )

                if score > best_score:

                    best_score = score

                    best_example = (
                        example[
                            "text"
                        ]
                    )

            if best_example is None:
                continue

            scored_matches.append(
                (
                    best_score,
                    recipe,
                    best_example,
                )
            )

        if not scored_matches:
            return None

        scored_matches.sort(
            key=lambda item:
                item[0],
            reverse=True,
        )

        (
            best_score,
            best_recipe,
            best_example,
        ) = scored_matches[0]

        # -----------------------------------------
        # Minimum confidence
        # -----------------------------------------

        if (
            best_score
            < self.threshold
        ):
            return None

        # -----------------------------------------
        # Ambiguity protection
        # -----------------------------------------

        if len(
            scored_matches
        ) > 1:

            second_score = (
                scored_matches[
                    1
                ][0]
            )

            margin = (
                best_score
                - second_score
            )

            if (
                margin
                < self.min_margin
            ):
                return None

        return RecipeMatch(
            recipe_id=(
                best_recipe["id"]
            ),

            name=(
                best_recipe["name"]
            ),

            objective=(
                best_recipe[
                    "objective"
                ]
            ),

            recipe=(
                best_recipe[
                    "recipe"
                ]
            ),

            score=(
                round(
                    best_score,
                    4,
                )
            ),

            matched_example=(
                best_example
            ),
        )