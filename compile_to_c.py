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
