# Installation

## Prerequisites

*   **Python:** Version 3.8 or higher.
    
*   **OS:** Windows, macOS, or Linux.
    

**Option 1: Install via PyPI (Recommended)**

The easiest way to install Netwatch is via pip. This will automatically install all required dependencies (like textual and psutil).

pip install netwatchpy

**Option 2: Install from Source**

If you want the latest development version or want to contribute to the code:

1.  Clone the repository: ```git clone https://github.com/Destroyer795/Netwatchpy-package.git```

2. Go inside the folder ```cd Netwatchpy-package```
    
3.  Install in editable mode: ```pip install -e .```
    

**Upgrading**

If you already have Netwatch installed and want to get the latest features (like the new SQLite database), run:

`pip install --upgrade netwatchpy`

> **Note on Migration:** If you are upgrading from an older version (v0.3.x), Netwatch will automatically detect your old quota.json file and migrate your history to the new SQLite database on the first launch. You won't lose any data!