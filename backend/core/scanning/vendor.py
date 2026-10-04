import logging
import os


LOGGER = logging.getLogger(__name__)
CORE_DIR = os.path.dirname(os.path.dirname(__file__))
MANUF_PATHS = (
    os.path.join(CORE_DIR, "resources", "manuf"),
    os.path.abspath(
        os.path.join(
            CORE_DIR,
            "..",
            "..",
            "macos",
            "LanGuardMac",
            "Resources",
            "manuf",
        )
    ),
)


def mac_bytes(mac):
    parts = (mac or "").replace("-", ":").split(":")
    if len(parts) != 6:
        return None
    try:
        return bytes(int(part, 16) for part in parts)
    except ValueError:
        return None


def is_locally_administered_mac(mac):
    raw = mac_bytes(mac)
    return bool(raw and raw[0] & 0x02)


class ManufVendorDB:
    _entries = None

    @classmethod
    def entries(cls):
        if cls._entries is None:
            cls._entries = cls.load_entries()
        return cls._entries

    @classmethod
    def load_entries(cls):
        entries = []
        for path in MANUF_PATHS:
            if not os.path.exists(path):
                continue
            try:
                with open(path, encoding="utf-8") as manuf_file:
                    for line in manuf_file:
                        entry = cls.parse_line(line)
                        if entry:
                            entries.append(entry)
            except OSError as exc:
                LOGGER.debug("Failed reading manuf database %s: %s", path, exc)
            if entries:
                break
        return sorted(entries, key=lambda item: item[1], reverse=True)

    @staticmethod
    def parse_line(line):
        line = line.strip()
        if not line or line.startswith("#"):
            return None
        parts = line.split(None, 2)
        if len(parts) < 2:
            return None
        prefix_text = parts[0]
        vendor = parts[2].strip() if len(parts) > 2 else parts[1].strip()
        if not vendor:
            return None
        if "/" in prefix_text:
            prefix_text, bits_text = prefix_text.split("/", 1)
            try:
                prefix_bits = int(bits_text)
            except ValueError:
                return None
        else:
            prefix_bits = len(prefix_text.replace(":", "").replace("-", "")) * 4
        try:
            prefix_value = int(prefix_text.replace(":", "").replace("-", ""), 16)
        except ValueError:
            return None
        prefix_hex_bits = len(prefix_text.replace(":", "").replace("-", "")) * 4
        if prefix_hex_bits > prefix_bits:
            prefix_value >>= prefix_hex_bits - prefix_bits
        return prefix_value, prefix_bits, vendor

    @classmethod
    def lookup(cls, mac):
        raw = mac_bytes(mac)
        if not raw or is_locally_administered_mac(mac):
            return ""
        mac_value = int.from_bytes(raw, "big")
        for prefix_value, prefix_bits, vendor in sorted(
            cls.entries(),
            key=lambda item: item[1],
            reverse=True,
        ):
            shift = 48 - prefix_bits
            if shift < 0:
                continue
            if (mac_value >> shift) == prefix_value:
                return vendor
        return ""


def manuf_vendor(mac):
    return ManufVendorDB.lookup(mac)
