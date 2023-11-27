FROM python:3.11

ARG USERNAME
ARG UID
ENV USERNAME=${USERNAME:-python}
ENV UID=${UID:-40000}

LABEL org.label-schema.schema-version = "1.0"
LABEL org.label-schema.name "Azure Python SMTP Relay Service"
LABEL org.label-schema.vendor "LearningToPi.com"
LABEL org.label-schema.description "Python service to relay email from SMTP clients using Azure Communication Service."
LABEL org.label-schema.usage "/app/README.md"
LABEL org.label-schema.url = "https://www.learningtopi.com/python-modules-applications/azure_smtp_relay/"
LABEL org.label-schema.vcs-url = "https://github.com/LearningToPi/azure_smtp_relay/tree/v1.0.0"
LABEL org.label-schema.vcs-ref = "0965349"
LABEL org.label-schema.version = "1.0.1"
LABEL org.label-schema.release = "py3.11-1"
LABEL org.label-schema.architecture = "amd64"
LABEL org.label-schema.changelog-url = "https://github.com/LearningToPi/azure_smtp_relay/blob/main/release_notes/v1.0.0.md"

LABEL org.label-schema.docker.cmd = 'docker run --name azure_smtp_relay -d -p 25:10025 -v config.toml:/app/config.toml learningtopi/azure_smtp_relay --subnets 192.168.0.0/16 --domains my-email-domain.com'
LABEL org.label-schema.docker.cmd.devel = 'docker run --name azure_smtp_relay -d -p 25:10025 -v config.toml:/app/config.toml learningtopi/azure_smtp_relay --subnets 192.168.0.0/16 --domains my-email-domain.com --log-level DEBUG'
LABEL org.label-schema.docker.cmd.help = "docker run --rm -it learningtopi/azure_smtp_relay --help"

EXPOSE 10025/tcp
VOLUME /apps
WORKDIR /apps

RUN adduser --disabled-password --gecos '' $USERNAME -u $UID
RUN mkdir /app && chown $USERNAME:$USERNAME /app
USER $USERNAME:$USERNAME

ADD requirements.txt /app
ADD entrypoint.sh /app
ADD README.md /app
ENV PYTHONPATH="/app"
RUN pip3 install -r /app/requirements.txt


ENTRYPOINT ["/app/entrypoint.sh"]
CMD []