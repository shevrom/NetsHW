import ipaddress
import struct

TYPE_NAMES = {
    1: "A",
    2: "NS",  # Name server
    5: "CNAME",
    12: "PTR",
    15: "MX",
    28: "AAAA",
}


# восстанавливает доменное имя из пакета, включая сжатые имена
def decode_name(packet: bytes, offset: int) -> tuple[str, int]:
    labels = []
    position = offset  # откуда начинаем читать тело запроса
    next_offset = None
    visited = set()

    # читаем первый байт (это может быть как размер, так и указатель), если просто размер, то читаем метку
    while True:
        if position >= len(packet):
            raise ValueError("DNS name goes beyond packet")

        # Защита от циклических указателей.
        if position in visited:
            raise ValueError("DNS compression pointer loop")
        visited.add(position)

        length = packet[position]

        # Старшие два бита 11 означают указатель.
        if length & 0xC0 == 0xC0:  # маска первых двух битов
            if position + 1 >= len(packet):
                raise ValueError("Incomplete DNS compression pointer")

            pointer = (
                    ((length & 0x3F) << 8)
                    | packet[position + 1]
            )  # берем 6 бит кроме первых двух 11 (указатель), смещаем на 8 разрядов влево, и заполняем вторым байтом

            if pointer >= len(packet):
                raise ValueError("DNS pointer outside packet")

            # Запоминаем, где продолжать разбор исходного поля.
            if next_offset is None:
                next_offset = position + 2  # текущая позиция + 2 - начало байта после 2 байтов смещения

            position = pointer
            continue

        # Значения 01xxxxxx и 10xxxxxx зарезервированы.
        if length & 0xC0:
            raise ValueError("Unsupported DNS label encoding")

        # Нулевая длина завершает имя.
        if length == 0:
            if next_offset is None:
                next_offset = position + 1
            break

        # Обычная метка: длина, затем её байты.
        start = position + 1
        end = start + length

        if end > len(packet):
            raise ValueError("DNS label goes beyond packet")

        label = packet[start:end].decode(
            "ascii",
            errors="replace",
        )
        labels.append(label)

        position = end

    return ".".join(labels) or ".", next_offset


# использует decode_name, чтобы прочитать одну DNS-запись: имя, тип, класс, TTL и данные
def parse_record(packet: bytes, offset: int) -> tuple[dict, int]:
    # Читаем имя записи.
    name, offset = decode_name(packet, offset)

    # После имени должно остаться минимум 10 байт:
    # TYPE (2), CLASS (2), TTL (4), RDLENGTH (2).
    if offset + 10 > len(packet):
        raise ValueError("Incomplete DNS resource record")

    rtype, rclass, ttl, rdlength = struct.unpack_from(
        "!HHIH",
        packet,
        offset,
    )  # I - 4 байта для TTL (время жизни в кэше)
    offset += 10

    # Проверяем, помещаются ли данные в пакет.
    rdata_start = offset
    rdata_end = rdata_start + rdlength

    if rdata_end > len(packet):
        raise ValueError("RDATA goes beyond packet")

    raw_data = packet[rdata_start:rdata_end]

    # Интерпретируем данные в зависимости от типа.
    if rtype == 1:  # A
        if rdlength != 4:
            raise ValueError("Invalid A record length")
        data = str(ipaddress.ip_address(raw_data))

    elif rtype == 28:  # AAAA
        if rdlength != 16:
            raise ValueError("Invalid AAAA record length")
        data = str(ipaddress.ip_address(raw_data))

    elif rtype in (2, 5, 12):  # NS, CNAME, PTR
        data, consumed = decode_name(packet, rdata_start)

        if consumed > rdata_end:
            raise ValueError("Name exceeds RDATA")

    elif rtype == 15:  # MX
        if rdlength < 3:
            raise ValueError("Invalid MX record length")

        preference = struct.unpack_from(
            "!H", packet, rdata_start
        )[0]

        exchange, consumed = decode_name(
            packet, rdata_start + 2
        )

        if consumed > rdata_end:
            raise ValueError("MX exchange exceeds RDATA")

        data = {
            "preference": preference,
            "exchange": exchange,
        }

    else:
            data = raw_data.hex(" ")

    record = {
        "name": name,
        "type": rtype,
        "type_name": TYPE_NAMES.get(rtype, f"TYPE{rtype}"),
        "class": rclass,
        "ttl": ttl,
        "rdlength": rdlength,
        "data": data,
    }

    return record, rdata_end

# Формат ответа:
# Header — заголовок.
# Question — вопрос, который мы отправили.
# Answer — найденные записи.
# Authority — информация об авторитетных серверах.
# Additional — дополнительные данные.
def parse_dns_packet(packet: bytes) -> dict:
    if len(packet) < 12: # Заголовок составляет первые 12 байт
        raise ValueError("DNS packet is shorter than header")

    request_id, flags, qdcount, ancount, nscount, arcount = (
        struct.unpack_from("!HHHHHH", packet, 0)
    ) # Считали заголовок

    offset = 12
    questions = []

    # Сначала разбираем секцию вопросов
    for _ in range(qdcount):
        name, offset = decode_name(packet, offset)

        if offset + 4 > len(packet):
            raise ValueError("Incomplete DNS question")

        qtype, qclass = struct.unpack_from(
            "!HH", packet, offset
        )
        offset += 4

        questions.append({
            "name": name,
            "type": qtype,
            "type_name": TYPE_NAMES.get(qtype, f"TYPE{qtype}"),
            "class": qclass,
        })

    # Затем последовательно разбираем три секции записей.
    sections = {}

    for section_name, count in (
        ("answers", ancount),
        ("authority", nscount),
        ("additional", arcount),
    ):
        records = []

        for _ in range(count):
            record, offset = parse_record(packet, offset)
            records.append(record)

        sections[section_name] = records

    return {
        "id": request_id,
        "flags": flags,
        "qr": (flags >> 15) & 1, # самый сатрший бит qr: 0 - запрос, 1 - ответ
        "rcode": flags & 0x000F, # последние 4 байта показывают результат обработки запроса (0 - NOERROR)
        "questions": questions,
        **sections,
    }