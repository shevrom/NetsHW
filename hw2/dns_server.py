import socket

from dns_parser import parse_dns_packet
from resolver import resolve_iteratively


HOST = "127.0.0.1"
PORT = 5300


def prepare_client_response(
    client_request: bytes,
    upstream_response: bytes,
) -> bytes:
    """Подготавливает ответ внешнего DNS-сервера клиенту."""

    response = bytearray(upstream_response)

    # У внешнего DNS-сервера был свой ID.
    # Возвращаем ID исходного запроса клиента.
    response[0:2] = client_request[0:2] # заменяем айди запроса сервера, на айди клиента

    # Копируем флаг RD из запроса клиента.
    client_flags = int.from_bytes(client_request[2:4], "big")
    response_flags = int.from_bytes(response[2:4], "big")

    response_flags |= 0x8000  # QR = 1: это ответ
    response_flags |= 0x0080  # RA = 1: рекурсия поддерживается

    response_flags = (
        (response_flags & ~0x0100)
        | (client_flags & 0x0100)
    ) # копируем просто RD клиента, но все равно находим ему ответ конечный

    response[2:4] = response_flags.to_bytes(2, "big")

    return bytes(response)


def make_servfail_response(request: bytes) -> bytes:
    """Формирует простой ответ SERVFAIL при ошибке поиска."""

    response = bytearray(request)

    request_flags = int.from_bytes(request[2:4], "big")

    # QR = 1, сохраняем OPCODE и RD, RA = 1, RCODE = 2 (SERVFAIL).
    flags = (
        0x8000
        | (request_flags & 0x7900)
        | 0x0080
        | 0x0002
    )

    response[2:4] = flags.to_bytes(2, "big")

    # Обнуляем ANCOUNT, NSCOUNT и ARCOUNT.
    # QDCOUNT и секция вопроса сохраняются.
    response[6:12] = b"\x00" * 6

    return bytes(response)


def run_server():
    with socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
    ) as sock:
        sock.bind((HOST, PORT))

        print(f"DNS-сервер запущен на {HOST}:{PORT}")

        while True:
            request, client_address = sock.recvfrom(4096)

            print(f"\nЗапрос от клиента {client_address}")

            if len(request) < 12:
                print("Слишком короткий DNS-пакет")
                continue

            try:
                message = parse_dns_packet(request)

                questions = message["questions"]
                if len(questions) != 1:
                    raise ValueError(
                        "Ожидался один вопрос в DNS-запросе"
                    )

                question = questions[0]
                name = question["name"]
                qtype = question["type_name"]

                print(f"Вопрос: {name}, тип: {qtype}")

                upstream_response = resolve_iteratively(
                    name,
                    qtype,
                )

                response = prepare_client_response(
                    request,
                    upstream_response,
                )

            except (OSError, ValueError, RuntimeError, KeyError) as error:
                print(f"Ошибка обработки запроса: {error}")
                response = make_servfail_response(request)

            sock.sendto(response, client_address)
            print(f"Ответ отправлен клиенту {client_address}")


if __name__ == "__main__":
    run_server()