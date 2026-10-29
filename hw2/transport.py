import socket
import struct


def query_udp(
        server_ip: str,
        packet: bytes,
        port: int = 53,
        timeout: float = 3.0,
) -> bytes:
    with socket.socket(
            socket.AF_INET,  # IPv4
            socket.SOCK_DGRAM,  # UDP
    ) as sock:
        sock.settimeout(timeout)

        sock.sendto(packet, (server_ip, port))

        response, address = sock.recvfrom(4096)

        print(f"Ответ получен от {address[0]}:{address[1]}")
        return response


def query_tcp(
        server_ip: str,
        packet: bytes,
        port: int = 53,
        timeout: float = 3.0,
) -> bytes:
    """Отправляет DNS-запрос по TCP и получает ответ."""
    if len(packet) > 65535:
        raise ValueError("DNS message is too large for TCP")

    with socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
    ) as sock:
        sock.settimeout(timeout)
        sock.connect((server_ip, port))

        # DNS over TCP: перед сообщением идут 2 байта длины.
        sock.sendall(struct.pack("!H", len(packet)) + packet)

        length_bytes = recv_exact(sock, 2)
        response_length = struct.unpack("!H", length_bytes)[0]

        response = recv_exact(sock, response_length)

        print(f"Ответ получен по TCP от {server_ip}:{port}")
        return response


def recv_exact(sock: socket.socket, size: int) -> bytes:
    """Читает ровно size байт из TCP-соединения."""
    data = bytearray()

    while len(data) < size:
        chunk = sock.recv(size - len(data))

        if not chunk:
            if not data:
                raise EOFError("TCP connection closed")
            raise ConnectionError("Incomplete TCP message")

        data.extend(chunk)

    return bytes(data)
