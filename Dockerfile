FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN mkdir -p /app/ && rm -rf /etc/apt/sources.list && rm -rf /etc/apt/sources.list.d/*ubuntu*
COPY ./sources-22.04.list /etc/apt/sources.list
RUN cat /etc/apt/sources.list
RUN apt update && apt install -y apt-utils && apt install -y wget tree net-tools iputils-ping
WORKDIR /app
RUN wget -O ams_community.zip https://ghproxy.net/https://github.com/ant-media/Ant-Media-Server/releases/download/ams-v2.13.2/ant-media-server-community-2.13.2.zip
RUN wget -O install_ant-media-server.sh https://ghproxy.net/https://raw.githubusercontent.com/ant-media/Scripts/master/install_ant-media-server.sh && chmod +x install_ant-media-server.sh
RUN all_proxy=127.0.0.1:10808 ./install_ant-media-server.sh ams_community.zip && service antmedia start
EXPOSE 80 5080 5443 4200 1935 50000-60000 5000
RUN touch /var/log/antmedia/ant-media-server.log
CMD service antmedia start && tail -f /var/log/antmedia/ant-media-server.log
