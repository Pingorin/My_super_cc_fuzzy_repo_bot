#!/bin/bash

echo "🚀 Universal Deployment Setup (Tarika 2) Shuru ho raha hai..."

# 1. Server aur Codespace dono ke liye zaroori tools install karein
pip install Cython setuptools

# 2. Python script banayein jo code ko .c mein badlega aur .py ko hide karega
cat << 'EOF' > compile_to_c.py
import os
import shutil
from Cython.Build import cythonize

# In files ko lock nahi karna hai taaki bot start ho sake
DONT_TOUCH = ["bot.py", "compile_to_c.py", "universal_setup.py", "__init__.py"]

# Original code chhupane ke liye backup folder
os.makedirs("hidden_backup", exist_ok=True)

py_files = []
for root, dirs, files in os.walk("."):
    if ".git" in root or "hidden_backup" in root or "__pycache__" in root or "build" in root:
        continue
    for file in files:
        if file.endswith(".py") and file not in DONT_TOUCH:
            filepath = os.path.join(root, file)
            py_files.append(filepath)

if py_files:
    print("Cythonizing:", py_files)
    cythonize(py_files, compiler_directives={'language_level': "3"})
    
    # Original .py files ko backup folder mein bhej do taaki Git par push na ho
    for filepath in py_files:
        dest = os.path.join("hidden_backup", filepath.replace("./", ""))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(filepath, dest)
EOF

python3 compile_to_c.py

# 3. Har Server ke liye Auto-Builder Script banayein (universal_setup.py)
cat << 'EOF' > universal_setup.py
import os
from setuptools import setup, Extension

ext_modules = []
for root, dirs, files in os.walk("."):
    if ".git" in root or "hidden_backup" in root:
        continue
    for file in files:
        if file.endswith(".c"):
            filepath = os.path.join(root, file)
            modulename = filepath.replace("./", "").replace("/", ".").replace(".c", "")
            ext_modules.append(Extension(modulename, [filepath]))

if ext_modules:
    setup(ext_modules=ext_modules)
EOF

# 4. Server ke start hone ka Magical Script (start.sh)
cat << 'EOF' > start.sh
#!/bin/bash
echo "🔨 [Universal Engine] Server ke hisaab se .so files ban rahi hain..."
python3 universal_setup.py build_ext --inplace

echo "🧹 Kachra saaf ho raha hai..."
rm -rf build/

echo "🌐 Dummy Web Server Start (Port Checks ke liye)..."
python3 -m http.server ${PORT:-8080} --bind 0.0.0.0 &

echo "✅ [Universal Engine] Bot is starting now!"
python3 bot.py
EOF
chmod +x start.sh

# 5. Procfile (Heroku/Render ke normal deploy ke liye)
echo "worker: bash start.sh" > Procfile
echo "web: bash start.sh" >> Procfile

# 6. Dockerfile (Hugging Face / Koyeb ke Container deploy ke liye)
cat << 'EOF' > Dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y gcc python3-dev
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["bash", "start.sh"]
EOF

# 7. Git Security (Hide secret files from internet)
echo "hidden_backup/" > .gitignore
echo "*.so" >> .gitignore
echo "*.pyc" >> .gitignore
echo "build/" >> .gitignore
echo "*.session" >> .gitignore

# 8. GitHub par push karein
git add -A
git commit -m "🚀 Universal Master Deployment (Tarika 2) - Auto Compiler"
git push origin main --force

echo "🎉 Bhai! Kaam 100% Final ho gaya! Code Universal ban chuka hai."
