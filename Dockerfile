# Wybieramy lekką wersję obrazu z Pythonem
FROM python:3.11-slim

# Ustawiamy zmienną środowiskową aby nie buforować logów (Flask lepiej loguje)
ENV PYTHONUNBUFFERED=1

# Tworzymy katalog dla aplikacji i ustawiamy go jako roboczy
WORKDIR /app

# Kopiujemy pliki zależności
COPY requirements.txt .

# Instalujemy zależności
RUN pip install --no-cache-dir -r requirements.txt

# Kopiujemy cały kod aplikacji do kontenera
COPY . .

# Opcjonalnie: port na którym działa Flask (można go też zadeklarować w docker-compose)
EXPOSE 8000

# Domyślnie uruchamiamy aplikację Flask
CMD ["python", "app.py"]
