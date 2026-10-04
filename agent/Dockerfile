FROM python:3.12-slim

WORKDIR /app

COPY agent/requirements.txt agent/requirements.txt
RUN pip install --no-cache-dir -r agent/requirements.txt

COPY agent/ agent/

RUN mkdir -p data && \
    useradd --create-home --shell /bin/bash msgstack-agent && \
    chown -R msgstack-agent:msgstack-agent /app

USER msgstack-agent

EXPOSE 8010

CMD ["python", "-m", "agent.app"]
