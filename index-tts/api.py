import os
import time
import uuid
import base64
import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
from contextlib import asynccontextmanager
from typing import Optional, Dict, Union, Tuple

import uvicorn
import torch
import torchaudio
from fastapi import (
    FastAPI,
    File,
    UploadFile,
    BackgroundTasks,
    HTTPException,
    Form,
    Depends,
)
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from indextts.infer import IndexTTS

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("index-tts-api")

# 全局模型变量
model = None
# 音频缓存 {文本内容+参考音频哈希: 输出路径}
audio_cache: Dict[str, str] = {}

# 配置
MAX_TEXT_LENGTH = 500  # 最大文本长度
CACHE_SIZE_LIMIT = 100  # 最大缓存项数量


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理器"""
    # 启动时执行
    global model
    logger.info("开始加载模型...")

    try:
        model = IndexTTS(
            model_dir="checkpoints",
            cfg_path="checkpoints/config.yaml",
            is_fp16=True,
            use_cuda_kernel=True,
        )
        logger.info("模型加载成功")
    except Exception as e:
        logger.error(f"模型加载失败: {str(e)}")
        raise

    # 创建输出目录
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    yield

    # 关闭时执行
    logger.info("应用关闭中...")
    # 清理所有临时文件和缓存
    audio_cache.clear()
    logger.info("应用已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="IndexTTS API",
    description="工业级可控且高效的零样本文本转语音系统 API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# 添加CORS支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TTSRequest(BaseModel):
    text: str = Field(..., max_length=MAX_TEXT_LENGTH, description="要转换的文本内容")
    use_fast_mode: bool = Field(True, description="是否使用快速推理模式")


def validate_text(text: str = Form(...)):
    """验证输入文本"""
    if not text or len(text) > MAX_TEXT_LENGTH:
        raise HTTPException(
            status_code=400, detail=f"文本长度必须在1到{MAX_TEXT_LENGTH}字符之间"
        )
    return text


def get_cache_key(text: str, reference_file: str) -> str:
    """生成缓存键"""
    # 简单组合文本和文件路径的哈希作为键
    return f"{hash(text)}_{hash(reference_file)}"


def manage_cache():
    """管理缓存大小"""
    global audio_cache
    # 如果缓存超过限制，删除最早的一半项
    if len(audio_cache) > CACHE_SIZE_LIMIT:
        # 转换为列表并排序，保留较新的一半
        items = list(audio_cache.items())
        audio_cache = dict(items[len(items) // 2 :])


@app.get("/health")
async def health_check():
    """健康检查接口"""
    if model is None:
        return JSONResponse(
            status_code=503, content={"status": "error", "message": "模型未加载"}
        )
    return {"status": "ok", "message": "服务正常"}


@app.post("/synthesize")
async def synthesize(
    text: str = Depends(validate_text),
    use_fast_mode: bool = Form(True),
    reference_audio: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
):
    """
    文本转语音接口

    将输入文本根据参考音频的声音特征转换为语音。

    参数:
    - reference_audio: 参考音频文件（WAV格式），用于声音克隆
    - text: 要转换为语音的文本内容
    - use_fast_mode: 是否使用快速推理模式（适合长文本）

    返回:
    - 生成的WAV格式音频文件
    """
    if model is None:
        raise HTTPException(status_code=503, detail="模型未加载")

    # 检查音频文件格式
    if not reference_audio.filename.lower().endswith((".wav", ".mp3", ".flac")):
        raise HTTPException(
            status_code=400, detail="仅支持WAV、MP3或FLAC格式的参考音频"
        )

    try:
        # 保存上传的参考音频
        temp_reference = NamedTemporaryFile(delete=False, suffix=".wav")
        temp_reference.close()
        temp_path = temp_reference.name

        with open(temp_path, "wb") as f:
            content = await reference_audio.read()
            if not content:
                raise HTTPException(status_code=400, detail="参考音频文件为空")
            f.write(content)

        # 检查缓存
        cache_key = get_cache_key(text, temp_path)
        if cache_key in audio_cache and os.path.exists(audio_cache[cache_key]):
            logger.info(f"使用缓存: {cache_key}")
            # 设置清理临时文件的后台任务
            if background_tasks:
                background_tasks.add_task(os.unlink, temp_path)
            return FileResponse(
                audio_cache[cache_key],
                media_type="audio/wav",
                filename=os.path.basename(audio_cache[cache_key]),
            )

        # 生成输出路径
        output_filename = f"output_{int(time.time())}_{uuid.uuid4().hex[:8]}.wav"
        output_path = os.path.join("outputs", output_filename)

        # 执行推理
        start_time = time.time()
        logger.info(f"开始推理: 文本长度={len(text)}, 快速模式={use_fast_mode}")

        try:
            if use_fast_mode:
                result = model.infer_fast(temp_path, text, output_path)
            else:
                result = model.infer(temp_path, text, output_path)
        except Exception as e:
            logger.error(f"推理失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"语音生成失败: {str(e)}")

        logger.info(f"推理完成: 耗时={time.time() - start_time:.2f}秒")

        # 添加到缓存
        audio_cache[cache_key] = output_path
        manage_cache()

        # 设置清理临时文件的后台任务
        if background_tasks:
            background_tasks.add_task(os.unlink, temp_path)

        # 返回音频文件
        return FileResponse(
            output_path, media_type="audio/wav", filename=output_filename
        )

    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.exception("处理请求时发生错误")
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


@app.post("/synthesize_base64")
async def synthesize_base64(
    request: TTSRequest,
    reference_audio_base64: str,
    background_tasks: BackgroundTasks = None,
):
    """
    文本转语音接口（使用Base64编码的音频）

    将输入文本根据Base64编码的参考音频的声音特征转换为语音。

    参数:
    - reference_audio_base64: Base64编码的参考音频
    - text: 要转换为语音的文本内容
    - use_fast_mode: 是否使用快速推理模式（适合长文本）

    返回:
    - 包含Base64编码的生成音频
    """
    if model is None:
        raise HTTPException(status_code=503, detail="模型未加载")

    # 验证文本
    validate_text(request.text)

    try:
        # 解码Base64音频
        try:
            audio_data = base64.b64decode(reference_audio_base64)
            if not audio_data:
                raise ValueError("Base64数据解码失败或为空")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"无效的Base64编码: {str(e)}")

        # 保存参考音频
        temp_reference = NamedTemporaryFile(delete=False, suffix=".wav")
        temp_reference.close()
        temp_path = temp_reference.name

        with open(temp_path, "wb") as f:
            f.write(audio_data)

        # 检查缓存
        cache_key = get_cache_key(request.text, temp_path)
        cached_path = audio_cache.get(cache_key)

        if cached_path and os.path.exists(cached_path):
            logger.info(f"使用缓存: {cache_key}")
            # 读取缓存的音频并转换为Base64
            with open(cached_path, "rb") as audio_file:
                audio_bytes = audio_file.read()
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

            # 设置清理临时文件的后台任务
            if background_tasks:
                background_tasks.add_task(os.unlink, temp_path)

            return {"status": "success", "audio_base64": audio_base64}

        # 生成输出路径
        output_filename = f"output_{int(time.time())}_{uuid.uuid4().hex[:8]}.wav"
        output_path = os.path.join("outputs", output_filename)

        # 执行推理
        start_time = time.time()
        logger.info(
            f"开始推理(Base64): 文本长度={len(request.text)}, 快速模式={request.use_fast_mode}"
        )

        try:
            if request.use_fast_mode:
                result = model.infer_fast(temp_path, request.text, output_path)
            else:
                result = model.infer(temp_path, request.text, output_path)
        except Exception as e:
            logger.error(f"推理失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"语音生成失败: {str(e)}")

        logger.info(f"推理完成: 耗时={time.time() - start_time:.2f}秒")

        # 添加到缓存
        audio_cache[cache_key] = output_path
        manage_cache()

        # 读取生成的音频并转换为Base64
        with open(output_path, "rb") as audio_file:
            audio_bytes = audio_file.read()

        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        # 设置清理临时文件的后台任务
        if background_tasks:
            background_tasks.add_task(os.unlink, temp_path)

        return {"status": "success", "audio_base64": audio_base64}

    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.exception("处理Base64请求时发生错误")
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


# 设置CUDA线程数，避免占用过多资源
torch.set_num_threads(4)

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=7860, log_level="info")
