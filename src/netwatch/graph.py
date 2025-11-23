from .utils import get_size

def generate_ascii_chart(data, width=60):
    """
    Generates a text-based bar chart from DB data.
    data: list of (timestamp_str, up_bytes, down_bytes)
    """
    if not data:
        return "[i]No data available for the last 24 hours. (Try generating some traffic!)[/i]"

    # 1. Find the maximum value to scale the bars
    max_val = 0
    for row in data:
        total = row[1] + row[2]
        if total > max_val:
            max_val = total

    if max_val == 0:
        return "No traffic recorded."

    lines = []
    lines.append(f"{'TIME':<16} | {'USAGE DISTRIBUTION':<{width}} | {'TOTAL'}")
    lines.append("-" * (16 + width + 3 + 10))

    for row in data:
        ts, up, down = row
        total = up + down
        
        # Extract just HH:MM from "YYYY-MM-DD HH:MM"
        # Adjust index if your timestamp format differs, but standard ISO is YYYY-MM-DD HH:MM:SS
        time_label = ts[11:16] 

        # Calculate bar widths relative to max_val
        bar_len = int((total / max_val) * width)
        
        down_share = int((down / total) * bar_len) if total > 0 else 0
        up_share = bar_len - down_share

        # Unicode block characters
        bar_str = ("█" * down_share) + ("░" * up_share)
        
        human_size = get_size(total)
        lines.append(f"{time_label:<16} | {bar_str:<{width}} | {human_size}")

    lines.append("")
    lines.append("Legend: [b]█[/b] = Download, [b]░[/b] = Upload")
    return "\n".join(lines)