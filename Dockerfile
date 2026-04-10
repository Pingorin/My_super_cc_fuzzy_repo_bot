FROM python:3.10-slim

# Work directory set karna
WORKDIR /app

# Saari files copy karna
COPY . /app

RUN apt-get update && apt-get install -y git

# Requirements install karna
RUN pip install --no-cache-dir -r requirements.txt

# Hugging Face ka port expose karna
EXPOSE 7860

# Bot ko start karna
CMD ["python3", "bot.py"]
