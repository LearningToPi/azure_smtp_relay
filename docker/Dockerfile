FROM python:3.11

ARG USERNAME
ARG UID
ENV USERNAME=${USERNAME:-svc-portal}
ENV UID=${UID:-30002}

LABEL org.label-schema.name "svc-portal"
LABEL org.label-schema.description "Portal Service"
LABEL org.label-schema.vcs-url = ""
LABEL org.label-schema.docker.cmd 'docker run ....'

EXPOSE 8090/tcp
VOLUME /scripts
WORKDIR /scripts

RUN adduser --disabled-password --gecos '' $USERNAME -u $UID
RUN mkdir /app && chown $USERNAME:$USERNAME /app
USER $USERNAME:$USERNAME

ADD requirements.txt /app
ENV PYTHONPATH="/app"
RUN pip3 install -r /app/requirements.txt


ENTRYPOINT /scripts/entrypoint.sh

