FROM fedora:25

LABEL maintainer "Douglas Mendizábal <douglas@redrobot.io>"

RUN dnf upgrade -y
RUN dnf install -y rabbitmq-server

EXPOSE 5672 15672

CMD ["rabbitmq-server"]
