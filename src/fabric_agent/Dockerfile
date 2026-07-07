FROM python:3.13-slim
WORKDIR /app
COPY ./src/fabric_agent/requirements.txt /tmp/requirements.txt
RUN if [ -f /tmp/requirements.txt ]; then \
        pip install --no-cache-dir -r /tmp/requirements.txt; \
    else \
        echo "No requirements.txt found"; \
    fi
# Agent code, its /skills folder (domain flows) and the web UI ship in the image.
COPY ./src /app/src
ENV HOST=0.0.0.0
ENV PORT=8090
EXPOSE 8090
CMD ["python", "-m", "src.fabric_agent.server"]
