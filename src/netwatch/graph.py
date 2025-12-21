from .utils import get_size

def generate_ascii_chart(data, width=50):
    """
    Generates an informative traffic analysis chart showing hourly usage patterns.
    data: list of (timestamp_str, upload_bytes, download_bytes)
    """
    if not data:
        return "[i]No data available for the last 24 hours. (Try generating some traffic!)[/i]"

    # Aggregate statistics
    total_up = 0
    total_down = 0
    max_val = 0
    peak_hour = None
    peak_total = 0
    hour_details = []
    
    for row in data:
        ts, up, down = row
        total = up + down
        total_up += up
        total_down += down
        
        if total > max_val:
            max_val = total
            peak_hour = ts[11:13]
        if total > peak_total:
            peak_total = total
        
        hour_details.append((ts, up, down, total))

    if max_val == 0:
        return "No traffic recorded."

    # Calculate statistics
    avg_total = (total_up + total_down) / len(data) if data else 0
    total_combined = total_up + total_down
    download_pct = (total_down / total_combined * 100) if total_combined > 0 else 0

    lines = []
    
    # Header with summary
    lines.append("")
    lines.append("TRAFFIC SUMMARY (24 Hours)")
    lines.append("─" * 60)
    lines.append(f"Download: {get_size(total_down):<20} ({download_pct:.1f}%)")
    lines.append(f"Upload:   {get_size(total_up):<20} ({100-download_pct:.1f}%)")
    lines.append(f"Peak Hour: {peak_hour}:00 ({get_size(peak_total)})")
    lines.append(f"Average:  {get_size(int(avg_total))} per hour")
    lines.append("")
    
    # Traffic distribution by hour
    lines.append("HOURLY BREAKDOWN")
    lines.append("─" * 60)
    lines.append(f"{'TIME':<6} | {'USAGE':<{width}} | {'TOTAL':<12}")
    lines.append("─" * 60)

    for ts, up, down, total in hour_details:
        hour = ts[11:13]
        
        # Generate bar
        bar_len = int((total / max_val) * width) if max_val > 0 else 0
        
        # Calculate proportion
        if total > 0:
            down_len = int((down / total) * bar_len)
        else:
            down_len = 0
        up_len = bar_len - down_len
        
        # Create visual bars
        down_bar = "█" * down_len
        up_bar = "░" * up_len
        empty_bar = " " * (width - bar_len)
        
        bar_str = down_bar + up_bar + empty_bar
        
        # Mark peak hour
        marker = " (PEAK)" if total == peak_total else ""
        size_str = get_size(total)
        
        lines.append(f"{hour}:00  | {bar_str} | {size_str:<12}{marker}")

    lines.append("─" * 60)
    lines.append("")
    lines.append("Legend: █ = Download, ░ = Upload")
    
    return "\n".join(lines)