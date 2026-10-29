import socket
import struct
import threading

from dns_parser import parse_dns_packet
from transport import recv_exact
from resolver import resolve_iteratively
from multiply import make_multiply_response

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
    response[0:2] = client_request[0:2]  # заменяем айди запроса сервера, на айди клиента

    # Копируем флаг RD из запроса клиента.
    client_flags = int.from_bytes(client_request[2:4], "big")
    response_flags = int.from_bytes(response[2:4], "big")

    response_flags |= 0x8000  # QR = 1: это ответ
    response_flags |= 0x0080  # RA = 1: рекурсия поддерживается

    response_flags = (
            (response_flags & ~0x0100)
            | (client_flags & 0x0100)
    )  # копируем просто RD клиента, но все равно находим ему ответ конечный

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


def handle_request(request: bytes) -> bytes | None:
    """Общая логика DNS для UDP- и TCP-клиентов."""

    if len(request) < 12:
        return None

    try:
        message = parse_dns_packet(request)

        if message["qr"] != 0:
            return None

        questions = message["questions"]

        if len(questions) != 1:  # обрабатываем только один вопрос
            return make_servfail_response(request)

        question = questions[0]

        name = question["name"]
        qtype = question["type_name"]

        print(f"Запрос: {name} {qtype}")

        # Сначала проверяем multiply
        multiply_response = make_multiply_response(
            request, question
        )

        if multiply_response is not None:
            print("Сработало правило multiply")
            return multiply_response

        # Иначе выполняем обычный итеративный поиск
        upstream_response = resolve_iteratively(name, qtype)

        # Возвращаем ответ клиенту с его исходным ID
        return prepare_client_response(
            request,
            upstream_response,
        )

    except (
            OSError,
            ValueError,
            RuntimeError,
            KeyError,
            IndexError,
            struct.error,
    ) as error:
        print(f"Ошибка обработки запроса: {error}")
        return make_servfail_response(request)


def run_udp_server():
    with socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
    ) as sock:
        sock.bind((HOST, PORT))
        print(f"DNS UDP слушает {HOST}:{PORT}")

        while True:
            request, client_address = sock.recvfrom(65535)

            print(f"\nUDP-клиент: {client_address}")

            response = handle_request(request)

            if response is not None:
                sock.sendto(response, client_address)

def handle_tcp_client(
    connection: socket.socket,
    client_address: tuple,
):
    with connection:
        connection.settimeout(10.0)
        print(f"\nTCP-клиент: {client_address}")

        while True:
            try:
                # TCP-префикс: длина DNS-сообщения (2 байта).
                length_bytes = recv_exact(connection, 2)
                message_length = struct.unpack(
                    "!H", length_bytes
                )[0]

                if message_length < 12:
                    print("Некорректная длина DNS-сообщения")
                    return

                request = recv_exact(
                    connection, message_length
                )

                response = handle_request(request)

                if response is None:
                    return

                # Передаём длину ответа, затем сам DNS-пакет
                framed_response = (
                    struct.pack("!H", len(response))
                    + response
                )

                connection.sendall(framed_response)

            except EOFError:
                # Клиент штатно закрыл соединение.
                return
            except (
                OSError,
                ConnectionError,
                ValueError,
                struct.error,
            ) as error:
                print(f"Ошибка TCP: {error}")
                return

def run_tcp_server():
    with socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    ) as sock:

        sock.bind((HOST, PORT))
        sock.listen(1)

        print(f"DNS TCP слушает {HOST}:{PORT}")

        while True:
            connection, client_address = sock.accept()

            # Обрабатываем соединение последовательно.
            handle_tcp_client(connection, client_address)

def run_server():
    # UDP и TCP могут использовать один номер порта.
    udp_thread = threading.Thread(
        target=run_udp_server,
        daemon=True,
    )
    udp_thread.start()

    # Основной поток обслуживает TCP.
    run_tcp_server()

if __name__ == "__main__":
    run_server()
