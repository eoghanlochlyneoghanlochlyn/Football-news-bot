# ============================================================
# اندازهٔ واقعی تصویر
# ============================================================

def get_real_image_dimensions(image_url):

    if not image_url:
        return 0, 0

    try:

        response = requests.get(
            image_url,
            headers={
                **REQUEST_HEADERS,
                "Range": "bytes=0-65535",
            },
            timeout=IMAGE_REQUEST_TIMEOUT,
            stream=True,
            allow_redirects=True,
        )

        if not response.ok:
            return 0, 0

        content_type = (
            response.headers.get(
                "Content-Type",
                ""
            )
            .lower()
        )

        data = response.content

        # JPEG
        if (
            "image/jpeg" in content_type
            or image_url.lower()
            .split("?")[0]
            .endswith((".jpg", ".jpeg"))
        ):

            return get_jpeg_dimensions(data)

        # PNG
        if (
            "image/png" in content_type
            or image_url.lower()
            .split("?")[0]
            .endswith(".png")
        ):

            if (
                len(data) >= 24
                and data[:8]
                == b"\x89PNG\r\n\x1a\n"
            ):

                width = int.from_bytes(
                    data[16:20],
                    "big"
                )

                height = int.from_bytes(
                    data[20:24],
                    "big"
                )

                return width, height

        # GIF
        if (
            "image/gif" in content_type
            or image_url.lower()
            .split("?")[0]
            .endswith(".gif")
        ):

            if (
                len(data) >= 10
                and data[:6] in (
                    b"GIF87a",
                    b"GIF89a",
                )
            ):

                width = int.from_bytes(
                    data[6:8],
                    "little"
                )

                height = int.from_bytes(
                    data[8:10],
                    "little"
                )

                return width, height

        # WebP
        if (
            "image/webp" in content_type
            or image_url.lower()
            .split("?")[0]
            .endswith(".webp")
        ):

            return get_webp_dimensions(data)

        return 0, 0

    except Exception:

        return 0, 0


# ============================================================
# ابعاد JPEG
# ============================================================

def get_jpeg_dimensions(data):

    try:

        if len(data) < 2:
            return 0, 0

        if data[:2] != b"\xff\xd8":
            return 0, 0

        index = 2

        while index < len(data):

            if data[index] != 0xFF:

                index += 1
                continue

            while (
                index < len(data)
                and data[index] == 0xFF
            ):
                index += 1

            if index >= len(data):
                break

            marker = data[index]
            index += 1

            if marker in (0xD8, 0xD9):
                continue

            if index + 2 > len(data):
                break

            segment_length = int.from_bytes(
                data[index:index + 2],
                "big"
            )

            if segment_length < 2:
                break

            if marker in (
                0xC0,
                0xC1,
                0xC2,
                0xC3,
                0xC5,
                0xC6,
                0xC7,
                0xC9,
                0xCA,
                0xCB,
                0xCD,
                0xCE,
                0xCF,
            ):

                if index + 7 <= len(data):

                    height = int.from_bytes(
                        data[index + 3:index + 5],
                        "big"
                    )

                    width = int.from_bytes(
                        data[index + 5:index + 7],
                        "big"
                    )

                    return width, height

            index += segment_length

        return 0, 0

    except Exception:

        return 0, 0

# ============================================================
# ابعاد WebP
# ============================================================

def get_webp_dimensions(data):

    try:

        if (
            len(data) < 16
            or data[:4] != b"RIFF"
            or data[8:12] != b"WEBP"
        ):
            return 0, 0

        # VP8X
        if data[12:16] == b"VP8X":

            if len(data) < 30:
                return 0, 0

            width = (
                1
                + int.from_bytes(
                    data[24:27],
                    "little"
                )
            )

            height = (
                1
                + int.from_bytes(
                    data[27:30],
                    "little"
                )
            )

            return width, height

        # VP8
        if data[12:16] == b"VP8 ":

            if len(data) < 30:
                return 0, 0

            frame_start = data.find(
                b"\x9d\x01\x2a"
            )

            if frame_start != -1:

                pos = frame_start + 3

                if pos + 4 <= len(data):

                    width = int.from_bytes(
                        data[pos:pos + 2],
                        "little"
                    ) & 0x3FFF

                    height = int.from_bytes(
                        data[pos + 2:pos + 4],
                        "little"
                    ) & 0x3FFF

                    return width, height

        # VP8L
        if data[12:16] == b"VP8L":

            if len(data) < 25:
                return 0, 0

            if data[20] == 0x2F:

                bits = int.from_bytes(
                    data[21:25],
                    "little"
                )

                width = (
                    (bits & 0x3FFF)
                    + 1
                )

                height = (
                    ((bits >> 14) & 0x3FFF)
                    + 1
                )

                return width, height

        return 0, 0

    except Exception:

        return 0, 0


