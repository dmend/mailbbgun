FROM fedora:25

LABEL maintainer "Douglas Mendizábal <douglas@redrobot.io>"

RUN dnf upgrade -y
RUN dnf install -y https://yum.postgresql.org/9.6/fedora/fedora-25-x86_64/pgdg-fedora96-9.6-3.noarch.rpm
RUN dnf install -y postgresql96-server

USER postgres
RUN /usr/pgsql-9.6/bin/initdb -D /var/lib/pgsql/9.6/data
RUN echo -e "host\tall\t\tall\t\t0.0.0.0/0\t\tmd5" >> /var/lib/pgsql/9.6/data/pg_hba.conf
RUN echo "listen_addresses='*'" >> /var/lib/pgsql/9.6/data/postgresql.conf

EXPOSE 5432

CMD [ "/usr/pgsql-9.6/bin/postgres", "-D", "/var/lib/pgsql/9.6/data"]
