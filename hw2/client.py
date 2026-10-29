from dns_query import make_query
from dns_parser import parse_dns_packet
from transport import query_udp, query_tcp

SERVER_IP = "127.0.0.1"
SERVER_PORT = 5300

DOMAINS = (
    "2.22.multiply.test.com",
    "example.com",
)

PROTOCOLS = ("UDP", "TCP")


def ask_dns(name: str, protocol: str, request_id: int):
    query = make_query(
        name,
        "A",
        request_id,
    )

    if protocol == "UDP":
        response = query_udp(
            SERVER_IP,
            query,
            port=SERVER_PORT,
        )
    elif protocol == "TCP":
        response = query_tcp(
            SERVER_IP,
            query,
            port=SERVER_PORT,
        )
    else:
        raise ValueError(f"Unknown protocol: {protocol}")

    message = parse_dns_packet(response)

    if message["id"] != request_id:
        raise ValueError("DNS transaction ID mismatch")

    print(f"\n{'=' * 45}")
    print(f"Protocol: {protocol}")
    print(f"Domain:   {name}")
    print("RCODE:", message["rcode"]) # успех или ошибка

    if message["answers"]:
        for record in message["answers"]:
            print(
                record["name"],
                record["type_name"],
                record["data"],
                "TTL =", record["ttl"],
            )
    else:
        print("No answer records")


def main():
    request_id = 0x1234

    for name in DOMAINS:
        for protocol in PROTOCOLS:
            try:
                ask_dns(name, protocol, request_id)
            except (OSError, ValueError) as error:
                print(f"\nERROR: {protocol}, {name}: {error}")

            request_id = (request_id + 1) % 65536


if __name__ == "__main__":
    main()
