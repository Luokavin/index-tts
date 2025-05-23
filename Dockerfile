# 使用pytorch官方镜像
FROM pytorch/pytorch:2.6.0-cuda12.6-cudnn9-devel

# 设置工作目录
WORKDIR /app/index-tts

# 设置时区
ENV TZ=Asia/Shanghai

# 安装基础依赖
RUN apt update && apt install -y ffmpeg && apt clean && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY index-tts/ /app/index-tts/

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt && pip install deepspeed && rm -rf ~/.cache/pip/*

# 设置环境变量
ENV CUDA_HOME=/usr/local/cuda-12.6
ENV PATH=$CUDA_HOME/bin:$PATH
ENV LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH

# 下载模型
RUN pip install -U "huggingface_hub[cli]" && rm -rf ~/.cache/pip/*
RUN huggingface-cli download IndexTeam/IndexTTS-1.5 \
  config.yaml bigvgan_discriminator.pth bigvgan_generator.pth bpe.model dvae.pth gpt.pth unigram_12000.vocab \
  --local-dir checkpoints

# 安装webui
RUN pip install -e ".[webui]"

# 预加载模型
RUN python webui.py --preload-only

# 设置端口
EXPOSE 7860

# 指定默认可执行文件
CMD ["python", "api.py"]