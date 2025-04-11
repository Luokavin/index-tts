# 基础镜像
FROM ubuntu:22.04
# 防止安装依赖的时候要求确认配置
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai
RUN apt update && apt install -y apt-utils && apt install -y wget tree net-tools iputils-ping python3

# ant-media-server 安装
WORKDIR /app
RUN wget -O ams_community.zip https://github.com/ant-media/Ant-Media-Server/releases/download/ams-v2.13.2/ant-media-server-community-2.13.2.zip
RUN wget -O install_ant-media-server.sh https://raw.githubusercontent.com/ant-media/Scripts/master/install_ant-media-server.sh && chmod +x install_ant-media-server.sh
RUN ./install_ant-media-server.sh ams_community.zip && rm -rf ams_community.zip

# 替换为国内源
RUN mkdir -p /app/ && rm -rf /etc/apt/sources.list && rm -rf /etc/apt/sources.list.d/*ubuntu*
COPY ./sources-22.04.list /etc/apt/sources.list
RUN pip config set global.index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple

# 定义端口
EXPOSE 80 5080 5443 4200 1935 50000-60000 5000

RUN touch /var/log/antmedia/ant-media-server.log
CMD service antmedia start && tail -f /var/log/antmedia/ant-media-server.log
