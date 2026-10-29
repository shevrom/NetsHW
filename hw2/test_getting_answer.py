import socket

from dns_query import make_query
from hw2.dns_parser import parse_dns_packet
from transport import query_udp


ROOT_SERVER_IP = "198.41.0.4"


request_id = 0x1234

query = make_query(
    "example.com",
    "A",
    request_id,
)

print(f"Отправляем запрос корневому серверу {ROOT_SERVER_IP}:53")
print("Запрос:", query.hex(" "))

try:
    response = query_udp(ROOT_SERVER_IP, query)

    print("Получено байт:", len(response))
    print("Ответ:", response.hex(" "))

    message = parse_dns_packet(response)

    if message["id"] != request_id:
        raise ValueError("DNS transaction ID mismatch")

    if message["qr"] != 1:
        raise ValueError("Received packet is not a DNS response")

    print("\nРазобранный ответ:")
    print("ID:", hex(message["id"]))
    print("RCODE:", message["rcode"])
    print("Вопросы:", message["questions"])

    for section_name in ("answers", "authority", "additional"):
        print(f"\n{section_name}:")

        for record in message[section_name]:
            print(
                record["name"],
                record["type_name"],
                "TTL =", record["ttl"],
                "Data =", record["data"],
            )

except (socket.timeout, OSError, ValueError) as error:
    print(f"Ошибка: {error}")