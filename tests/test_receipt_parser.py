import json

from app.ai.receipt_parser import (
    ReceiptParser,
)


parser = ReceiptParser()

result = parser.parse(
    "tmp/receipt.jpg"
)


print("\n[Receipt Parser]")
print(
    json.dumps(
        result.model_dump(),
        ensure_ascii=False,
        indent=2,
    )
)