import struct

DNS_TYPES = {
    "A": 1, #IpV4
    "NS": 2,
    "CNAME": 5,
    "AAAA": 28, # IpV6
    "MX": 15,
}

# Формат: example.com -> 07 e x a m p l e 03 c o m 00 - байт длины + байты имени
def encode_name(name: str) -> bytes:
    result = bytearray()

    for label in name.rstrip(".").split("."):
        encoded = label.encode("idna")  # для кириллицы idna (Internationalized Domain Names in Applications)

        if len(encoded) > 63:  # первые 2 бита в 8 битах (байте) зарезервированы: 00xxxxxx — обычный label, длина 0–63
            raise ValueError("DNS label is too long")

        result.append(len(encoded))
        result.extend(encoded)

    result.append(0)
    return bytes(result)


def make_query(name: str, qtype: str, request_id: int) -> bytes:
    if qtype not in DNS_TYPES:
        raise ValueError("Unsupported DNS record type")

    if not 0 <= request_id <= 0xFFFF:
        raise ValueError("Invalid DNS transaction ID")

    header = struct.pack(
        "!HHHHHH", # ! - big-Endian, H - 2 байта, 6*2 = 12 байт в заголовке
        request_id,
        0x0000,  # QR = 0 - не ответ, Opcode = 0 - стандартный запрос, AA=0 - не авторитативный (только для ответа)
        # TC = 0 - не обрезан, RD=0 - НЕ РЕКУРСИЯ
        1,       # QDCOUNT
        0,       # ANCOUNT
        0,       # NSCOUNT
        0,       # ARCOUNT
    )

    question = encode_name(name) # Имя + тип запроса + класс (интернет)
    question += struct.pack("!HH", DNS_TYPES[qtype], 1) # 1 байт на тип и 1 на класс (1 - инет)

    return header + question
