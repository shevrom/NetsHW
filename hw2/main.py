
from resolver import resolve_iteratively

result = resolve_iteratively("example.com", "A")

print("\nИтоговые записи:")
for record in result["answers"]:
    print(
        record["name"],
        record["type_name"],
        record["data"],
        "TTL =", record["ttl"],
    )
