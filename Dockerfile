FROM pytorch/pytorch:2.6.0-cuda12.6-cudnn9-devel

WORKDIR /app/index-tts
ENV TZ=Asia/Shanghai

RUN apt update && apt install -y wget net-tools tree curl ffmpeg gcc g++ cmake && wget https://github.com/index-tts/index-tts/raw/refs/heads/main/requirements.txt && apt clean && rm -rf /var/lib/apt/lists/*
RUN  pip install -r requirements.txt && pip install deepspeed && rm -rf ~/.cache/pip/*

RUN pip install -U triton --index-url https://aiinfra.pkgs.visualstudio.com/PublicPackages/_packaging/Triton-Nightly/pypi/simple/triton-nightly && rm -rf ~/.cache/pip/*

ENV CUDA_HOME=/usr/local/cuda-12.6
ENV PATH=$CUDA_HOME/bin:$PATH
ENV LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH

# 设置国内源
RUN mkdir -p /app/index-tts && rm -rf /etc/apt/sources.list && rm -rf /etc/apt/sources.list.d/*ubuntu*
COPY sources-22.04.list /etc/apt/sources.list
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple
RUN pip config set install.trusted-host mirrors.aliyun.com

ENTRYPOINT ["python", "webui.py"]
