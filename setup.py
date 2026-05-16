import os
from setuptools import setup, Extension

extensions = []
for root, dirs, files in os.walk("."):
    for file in files:
        if file.endswith(".c"):
            file_path = os.path.join(root, file)
            mod_name = os.path.relpath(file_path, ".").replace(os.sep, ".").replace(".c", "")
            extensions.append(Extension(mod_name, [file_path]))

setup(
    name="UniversalBotEngine",
    version="1.0",
    ext_modules=extensions,
)
