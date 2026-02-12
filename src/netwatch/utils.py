def get_size(byte_val, use_bits=False):
    """
    Convert bytes into human readable string.
    If use_bits=True, converts to bits (multiply by 8) and uses 'b' suffix.
    """
    if byte_val is None:
        return "0 b" if use_bits else "0 B"
    
    val = byte_val * 8 if use_bits else byte_val
    suffix = "b" if use_bits else "B"
    
    power = 1024
    n = 0
    units = ["", "K", "M", "G", "T"]
    
    while val >= power and n < len(units) - 1:
        val /= power
        n += 1
        
    return f"{val:.2f} {units[n]}{suffix}"

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