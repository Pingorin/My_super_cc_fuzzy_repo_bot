# Python ka base image
FROM python:3.10-slim

# Working directory set karna
WORKDIR /app

# Files ko copy karna
COPY . /app

# GCC Compiler, Git, aur zaroori tools install karna
RUN apt-get update && apt-get install -y gcc build-essential git

# Python packages install karna
RUN pip install --no-cache-dir -r requirements.txt

# Hamara magic compiler code chalana
RUN python3 -c 'import os; from setuptools import setup, Extension; setup(name="E", ext_modules=[Extension(os.path.relpath(os.path.join(r, f), ".").replace(os.sep, ".")[:-2], [os.path.join(r, f)]) for r, d, fs in os.walk(".") if "venv" not in r for f in fs if f.endswith(".c")])' build_ext --inplace

# start.sh ko chalne ki permission dena
RUN chmod +x start.sh

# Hugging Face ko batana ki Port 7860 use karna hai
ENV PORT=7860

# Bot on karna
CMD ["bash", "start.sh"]
