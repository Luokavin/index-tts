FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-devel

WORKDIR /app/index-tts
ENV TZ=Asia/Shanghai

COPY requirements.txt ./
COPY sources.list /etc/apt/sources.list

RUN pip config set global.index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple && pip install -r requirements.txt && pip install deepspeed

RUN apt update && apt install -y ffmpeg gcc g++ cmake

RUN pip install -U triton --index-url https://aiinfra.pkgs.visualstudio.com/PublicPackages/_packaging/Triton-Nightly/pypi/simple/triton-nightly

ENV CUDA_HOME=/usr/local/cuda-12.4
ENV PATH=$CUDA_HOME/bin:$PATH
ENV LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
RUN mkdir -p /app/index-tts && rm -rf /etc/apt/sources.list && rm -rf /etc/apt/sources.list.d/*ubuntu*

ENTRYPOINT ["python", "webui.py"]
