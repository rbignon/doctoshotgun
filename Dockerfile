# Base image
FROM python:3.9.5-slim as base

# Build stage
FROM base as builder

# Dependency install directory
RUN mkdir /install
WORKDIR /install

# Install dependencies
COPY ./requirements.txt .
RUN pip install --prefix /install -r requirements.txt

# Run stage
FROM base

WORKDIR /usr/src/app

# Fetch dependencies from the build stage
COPY --from=builder /install /usr/local

COPY ./doctoshotgun.py .

# Entrypoint - Run the main script
ENTRYPOINT ["./doctoshotgun.py"]
