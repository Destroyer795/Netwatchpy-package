def get_size(byte_val):
    """Convert bytes into human readable string."""
    if byte_val is None:
        return "0 B"
    power = 1024
    n = 0
    units = ["", "K", "M", "G", "T"]
    while byte_val >= power and n < len(units) - 1:
        byte_val /= power
        n += 1
    return f"{byte_val:.2f} {units[n]}B"


def parse_limit(size_str):
    """Parse a string like '10GB' or '500MB' into bytes."""
    if not size_str:
        return None
    s = size_str.upper().strip()

    if s.endswith("GB"):
        return int(float(s[:-2]) * 1024**3)
    if s.endswith("MB"):
        return int(float(s[:-2]) * 1024**2)
    if s.endswith("KB"):
        return int(float(s[:-2]) * 1024)

    try:
        return int(float(s))
    except ValueError:
        return None
