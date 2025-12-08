# Use a lightweight Java image
FROM mysql:8.3.0
LABEL maintainer="santre8 <sandatetrejo8@hotmail.com>"


COPY ./init.sql /docker-entrypoint-initdb.d

EXPOSE 3306