FROM pytorch/pytorch:2.6.0-cuda12.6-cudnn9-devel

WORKDIR /app/index-tts
ENV TZ=Asia/Shanghai

RUN apt update && apt install -y wget net-tools tree curl && wget https://github.com/index-tts/index-tts/raw/refs/heads/main/requirements.txt
RUN  pip install -r requirements.txt && pip install deepspeed

RUN apt update && apt install -y ffmpeg gcc g++ cmake

RUN pip install -U triton --index-url https://aiinfra.pkgs.visualstudio.com/PublicPackages/_packaging/Triton-Nightly/pypi/simple/triton-nightly

ENV CUDA_HOME=/usr/local/cuda-12.4
ENV PATH=$CUDA_HOME/bin:$PATH
ENV LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH

# 设置国内源
RUN mkdir -p /app/index-tts && rm -rf /etc/apt/sources.list && rm -rf /etc/apt/sources.list.d/*ubuntu*
COPY sources-22.04.list /etc/apt/sources.list
RUN pip config set global.index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple

ENTRYPOINT ["python", "webui.py"]
