from enum import Enum


class PlanStatus(str, Enum):
    READY = "ready"
    NEEDS_CLARIFICATION = "needs_clarification"
    UNSUPPORTED = "unsupported"


class ActionType(str, Enum):
    CREATE_TRANSACTION = "create_transaction"
    UPDATE_TRANSACTION = "update_transaction"
    DELETE_TRANSACTION = "delete_transaction"

    QUERY_FINANCIAL_DATA = "query_financial_data"
    ANALYZE_FINANCIAL_DATA = "analyze_financial_data"

    CREATE_OBLIGATION = "create_obligation"
    UPDATE_OBLIGATION = "update_obligation"

    CREATE_GOAL = "create_goal"
    UPDATE_GOAL = "update_goal"

    SIMULATE_DECISION = "simulate_decision"

    UPDATE_PREFERENCE = "update_preference"

    CONVERSATION_RESPONSE = "conversation_response"


class FinancialNature(str, Enum):
    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"
    REFUND = "refund"
    INVESTMENT = "investment"
    DEBT = "debt"
    CASH_MOVEMENT = "cash_movement"
    ADJUSTMENT = "adjustment"
    UNKNOWN = "unknown"


class TransactionDirection(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"


class Metric(str, Enum):
    SPENDING = "spending"
    INCOME = "income"
    CASH_FLOW = "cash_flow"
    BALANCE = "balance"
    OBLIGATIONS = "obligations"
    SAVINGS = "savings"
    FLEXIBLE_SPENDING = "flexible_spending"
    TRANSACTION_COUNT = "transaction_count"


class PeriodType(str, Enum):
    CALENDAR_DAY = "calendar_day"
    CALENDAR_WEEK = "calendar_week"
    CALENDAR_MONTH = "calendar_month"
    CALENDAR_YEAR = "calendar_year"

    ROLLING_DAYS = "rolling_days"
    ROLLING_MONTHS = "rolling_months"

    ABSOLUTE_RANGE = "absolute_range"


class GroupBy(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"

    DAY_OF_WEEK = "day_of_week"

    CATEGORY = "category"
    SUBCATEGORY = "subcategory"
    MERCHANT = "merchant"
    ACCOUNT = "account"


class ComparisonType(str, Enum):
    PREVIOUS_PERIOD = "previous_period"
    USER_BASELINE = "user_baseline"
    CUSTOM_PERIOD = "custom_period"


class SortDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


class TransactionDateType(str, Enum):
    CALENDAR_DAY = "calendar_day"
    EXACT_DATE = "exact_date"