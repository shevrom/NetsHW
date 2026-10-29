from collections import deque

from dns_query import make_query
from transport import query_udp
from dns_parser import parse_dns_packet


ROOT_SERVER = "198.41.0.4"  # a.root-servers.net


def resolve_iteratively(
    name: str,
    qtype: str = "A",
    root_server: str = ROOT_SERVER,
    max_queries: int = 30,
):
    # Очередь IP-адресов DNS-серверов, которые ещё нужно проверить.
    servers = deque([root_server])

    # Чтобы не обращаться к одному серверу бесконечно.
    visited = set()

    request_id = 0x1234

    while servers and len(visited) < max_queries:
        server_ip = servers.pop()

        if server_ip in visited:
            continue

        visited.add(server_ip)

        print(f"\nЗапрашиваем {server_ip}:53")

        # сервер должен ответить сам или указать следующий сервер.
        query = make_query(
            name,
            qtype,
            request_id,
        )
        request_id = (request_id + 1) % 65536

        try:
            response = query_udp(server_ip, query)
            message = parse_dns_packet(response)
        except (OSError, ValueError) as error:
            print(f"Ошибка при запросе: {error}")
            continue

        # Если есть ответ, поиск завершён.
        if message["answers"]:
            print("Получен ответ!")
            return message

        print("Готового ответа нет, ищем следующий сервер.")

        # Имена серверов, ответственных за следующий уровень.
        nameservers = {
            record["data"].rstrip(".").lower()
            for record in message["authority"]
            if record["type_name"] == "NS"
        }

        # Ищем IPv4-адреса именно этих NS-серверов.
        # Это записи из секции additional.
        for record in message["additional"]:
            if (
                record["type_name"] == "A"
                and record["name"].rstrip(".").lower() in nameservers
            ):
                next_ip = record["data"]

                if next_ip not in visited:
                    print(
                        f"Следующий сервер: "
                        f"{record['name']} ({next_ip})"
                    )
                    servers.append(next_ip)

    raise RuntimeError(
        f"Не удалось получить ответ для {name} ({qtype}). "
        "Серверы закончились или превышен лимит запросов."
    )
