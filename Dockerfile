FROM python:3.9.5-slim

WORKDIR /usr/src/app

# Install dependencies
COPY ./requirements.txt .
RUN pip install -r requirements.txt

COPY ./doctoshotgun.py .

# Entrypoint - run the script
ENTRYPOINT ["./doctoshotgun.py"]
