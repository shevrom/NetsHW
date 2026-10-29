from dns_query import make_query
from transport import query_udp
from dns_parser import parse_dns_packet


SERVER_IP = "127.0.0.1"
SERVER_PORT = 5300


def main():
    query = make_query(
        "example.com",
        "A",
        request_id=0xBEEF,
    )

    response = query_udp(
        SERVER_IP,
        query,
        port=SERVER_PORT,
    )

    message = parse_dns_packet(response)

    print("\nОтвет DNS-сервера:")

    for record in message["answers"]:
        print(
            record["name"],
            record["type_name"],
            record["data"],
            "TTL =", record["ttl"],
        )


if __name__ == "__main__":
    main()