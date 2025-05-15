# 使用pytorch官方镜像
FROM pytorch/pytorch:2.6.0-cuda12.6-cudnn9-devel

# 设置工作目录
WORKDIR /app/index-tts

# 设置时区
ENV TZ=Asia/Shanghai

# 安装基础依赖和git，并克隆项目
RUN apt update && apt install -y wget net-tools tree curl ffmpeg gcc g++ cmake git && apt clean && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/index-tts/index-tts.git .

# 安装Python依赖
RUN pip install -r requirements.txt && pip install deepspeed && rm -rf ~/.cache/pip/*
RUN pip install -U triton --index-url https://aiinfra.pkgs.visualstudio.com/PublicPackages/_packaging/Triton-Nightly/pypi/simple/triton-nightly && rm -rf ~/.cache/pip/*

# 设置环境变量
ENV CUDA_HOME=/usr/local/cuda-12.6
ENV PATH=$CUDA_HOME/bin:$PATH
ENV LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH

# 下载模型
RUN pip install -U "huggingface_hub[cli]" && rm -rf ~/.cache/pip/*
RUN huggingface-cli download IndexTeam/Index-TTS --local-dir ./checkpoints

# 指定默认可执行文件
ENTRYPOINT ["python", "webui.py"]