FROM python:3.11-slim

# iptables binary is called at runtime via subprocess
# No other dependencies — blocker.py uses stdlib only
RUN apt-get update \
    && apt-get install -y --no-install-recommends iptables \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY blocker.py .

ENTRYPOINT ["python", "blocker.py"]
