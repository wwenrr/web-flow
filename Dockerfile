FROM accetto/ubuntu-vnc-xfce-g3:latest

ENV LANG=C.UTF-8
ENV TZ=Asia/Ho_Chi_Minh

USER 0

RUN apt-get update && apt-get install -y curl wget vim git nano openssh-server net-tools python3 python3-pip && apt-get clean

RUN pip3 install --break-system-packages --ignore-installed urllib3 poetry

RUN mkdir /var/run/sshd

RUN echo 'root:1415' | chpasswd

RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' /etc/pam.d/sshd

EXPOSE 22 5901 6901

WORKDIR /workspace
ENTRYPOINT ["bash", "-lc"]
CMD ["bash /workspace/entrypoint.sh"]
