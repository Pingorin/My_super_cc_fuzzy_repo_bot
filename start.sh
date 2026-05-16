#!/bin/bash
export PYTHONUNBUFFERED=1

echo "🔧 Renaming compiled .so files..."
find . -type f -name "*.so" | while read so_file; do
    dir_name=$(dirname "$so_file")
    filename=$(basename "$so_file")
    base_name="${filename%%.*}"
    if [ "$filename" != "$base_name.so" ]; then
        mv "$so_file" "$dir_name/$base_name.so"
    fi
done

echo "📂 Enforcing __init__.py rules..."
mkdir -p database plugins/compiled
touch database/__init__.py
touch plugins/__init__.py
touch plugins/compiled/__init__.py

find plugins -maxdepth 1 -type f -name "*.py" ! -name "__init__.py" -delete

echo "✨ Wrappers ban rahe hain..."
find plugins -maxdepth 1 -name "*.so" | while read so_file; do
    filename=$(basename "$so_file")
    base_name="${filename%%.*}"
    mv "$so_file" "plugins/compiled/$base_name.so"
    echo "from .compiled.$base_name import *" > "plugins/$base_name.py"
done

echo "✅ [Universal Engine] Bot is starting now!"
python3 -u bot.py
