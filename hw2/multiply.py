import struct

from dns_query import encode_name


def make_multiply_response(
    request: bytes,
    question: dict,
) -> bytes | None:
    """Формирует A-ответ для доменов вида 2.22.multiply.test.com."""

    # Специальное правило относится к IPv4-запросам класса IN.
    if question["type"] != 1 or question["class"] != 1:
        return None

    name = question["name"] # 2.22.multiply.test.com
    labels = name.rstrip(".").split(".") # [2, 22, multiply, test, com]
    lower_labels = [label.lower() for label in labels]

    try:
        multiply_index = lower_labels.index("multiply")
    except ValueError:
        # Обычный домен: потребуется итеративный поиск.
        return None

    numbers = labels[:multiply_index]

    if not numbers or not all(
        label.isascii() and label.isdigit()
        for label in numbers
    ):
        raise ValueError("Invalid labels before multiply") # не числа перед мультипл

    # Считаем произведение по модулю 256.
    value = 1

    for label in numbers:
        value = (value * int(label)) % 256

    request_id, request_flags = struct.unpack_from(
        "!HH", request, 0
    )

    # QR=1, RD сохраняется от клиента, RA=1.
    flags = 0x8000 | 0x0080 | (request_flags & 0x7900)

    header = struct.pack(
        "!HHHHHH",
        request_id,
        flags,
        1,  # QDCOUNT: один вопрос
        1,  # ANCOUNT: один ответ
        0,  # NSCOUNT: нет записей authority
        0,  # ARCOUNT: нет дополнительных записей
    )

    # Восстанавливаем вопрос в формате DNS.
    question_wire = encode_name(name)
    question_wire += struct.pack(
        "!HH",
        question["type"],
        question["class"],
    )

    # C0 0C — указатель на имя в начале секции вопроса.
    # TYPE=A, CLASS=IN, TTL=60, RDLENGTH=4.
    answer = (
        b"\xc0\x0c"
        + struct.pack("!HHIH", 1, 1, 60, 4) # Type, class, ttl, rdlength
        + bytes([127, 0, 0, value])
    )

    return header + question_wire + answer