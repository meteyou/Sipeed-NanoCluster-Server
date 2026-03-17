FROM python@sha256:14ab73bd56794689c00cce8162da1eb71925b188299f35f81717ec23816a5dea AS base

LABEL org.opencontainers.image.source="https://github.com/meteyou/sipeed-nanocluster-server"
LABEL org.opencontainers.image.description="Contains the base environment to run the server and the agent for temperature and fan control."

RUN wget -O raspberrypi.gpg.key https://archive.raspberrypi.com/debian/raspberrypi.gpg.key && apt-key add raspberrypi.gpg.key && \
     echo 'deb http://archive.raspberrypi.org/debian/ bookworm main'>> /etc/apt/sources.list.d/raspberry.list

RUN apt update -y && apt upgrade -y && pip3 install --upgrade pip && apt install python3-pigpio pigpio bash git -y && \
    mkdir -p /app

WORKDIR /app

ENTRYPOINT ["/usr/bin/pigpiod"]

FROM base AS temp-control-app

LABEL org.opencontainers.image.source="https://github.com/meteyou/sipeed-nanocluster-server"
LABEL org.opencontainers.image.description="Contains the environment to run the server and the agent for temperature and fan control."

USER 0

RUN --mount=type=bind,source=requirements.txt,target=/app/requirements.txt \
    pip3 install --requirement /app/requirements.txt

COPY src/templates ./templates
COPY src/static ./static
COPY src/server*.py .
COPY src/agent*.py .
COPY ./agent_config.yaml.example agent_config.yaml.example
COPY ./config.yaml.example config.yaml.example

COPY --chmod=555 ./docker/docker-entrypoint.sh /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
