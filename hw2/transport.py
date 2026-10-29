import socket


def query_udp(
    server_ip: str,
    packet: bytes,
    port: int = 53,
    timeout: float = 3.0,
) -> bytes:
    with socket.socket(
        socket.AF_INET, #IPv4
        socket.SOCK_DGRAM, #UDP
    ) as sock:
        sock.settimeout(timeout)

        sock.sendto(packet, (server_ip, port))

        response, address = sock.recvfrom(4096)

        print(f"Ответ получен от {address[0]}:{address[1]}")
        return response