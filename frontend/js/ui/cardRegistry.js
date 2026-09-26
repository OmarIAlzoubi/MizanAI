export const CARD_REGISTRY = {
    spending: {
        title: "الإنفاق هذا الشهر",
        description: "اتجاه إنفاقك من بداية الشهر حتى آخر بيانات متاحة",
        accent: "green",
        category: "الإنفاق",
        defaultSize: "medium",
        sizes: ["small", "medium", "large"],
    },

    concepts: {
        title: "أبرز التصنيفات",
        description: "المفاهيم الأكثر ظهورًا في عمليات الإنفاق",
        accent: "violet",
        category: "التحليل",
        defaultSize: "medium",
        sizes: ["small", "medium", "large"],
    },

    merchants: {
        title: "أعلى التجار",
        description: "الجهات الأعلى في الإنفاق خلال الفترة الحالية",
        accent: "amber",
        category: "الإنفاق",
        defaultSize: "medium",
        sizes: ["small", "medium", "large"],
    },

    daily: {
        title: "المصروف اليومي",
        description: "نظرة على آخر 7 أيام من البيانات المتاحة",
        accent: "blue",
        category: "التحليل",
        defaultSize: "medium",
        sizes: ["small", "medium", "large"],
    },

    cashflow: {
        title: "التدفق النقدي",
        description: "الأموال الداخلة مقابل الخارجة",
        accent: "rose",
        category: "التدفق",
        defaultSize: "medium",
        sizes: ["small", "medium", "large"],
    },

    metrics: {
        title: "مؤشرات سريعة",
        description: "عدد العمليات والمتوسط وأكبر عملية وآخر يوم بيانات",
        accent: "green",
        category: "الملخص",
        defaultSize: "medium",
        sizes: ["small", "medium", "large"],
    },

    monthly_comparison: {
        title: "مقارنة الأشهر",
        description: "قارن نفس المدة عبر آخر الأشهر المتاحة",
        accent: "blue",
        category: "التحليل",
        defaultSize: "medium",
        sizes: ["small", "medium", "large"],
        isNew: true,
    },

    bnpl: {
        title: "التقسيط BNPL",
        description: "إجمالي ومدفوعات التقسيط مثل Tabby وTamara",
        accent: "amber",
        category: "الالتزامات",
        defaultSize: "small",
        sizes: ["small", "medium", "large"],
        isNew: true,
    },

    coffee: {
        title: "القهوة",
        description: "إجمالي إنفاقك وعملياتك المرتبطة بالقهوة",
        accent: "coffee",
        category: "العادات",
        defaultSize: "small",
        sizes: ["small", "medium", "large"],
        isNew: true,
    },

    largest_transactions: {
        title: "أكبر العمليات",
        description: "أعلى عمليات الإنفاق خلال الفترة الحالية",
        accent: "rose",
        category: "الإنفاق",
        defaultSize: "medium",
        sizes: ["small", "medium", "large"],
        isNew: true,
    },

};


export const DEFAULT_ORDER = [
    "spending",
    "concepts",
    "merchants",
    "daily",
    "cashflow",
    "metrics",
];


export const DEFAULT_ENABLED = [
    ...DEFAULT_ORDER,
];
