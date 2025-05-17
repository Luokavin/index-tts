# Copyright (c) 2024 NVIDIA CORPORATION.
#   Licensed under the MIT license.

import torch
import torch.nn as nn
import os
import importlib.util
import sys
import pathlib
# load fused CUDA kernel: this enables importing anti_alias_activation_cuda
from indextts.BigVGAN.alias_free_activation.torch.resample import DownSample1d, UpSample1d

# 先尝试直接加载预编译的算子
try:
    from indextts.BigVGAN.alias_free_activation.cuda import load
    cuda_path = pathlib.Path(load.__file__).parent.absolute()
    build_path = cuda_path / "build"
    so_file = build_path / "anti_alias_activation_cuda.so"
    
    print(f"CUDA算子路径检查: {so_file} 存在={so_file.exists()}")
    
    # 尝试加载算子
    anti_alias_activation_cuda = load.load()
    print("成功加载CUDA算子")
    USE_CUDA_KERNEL = True
except Exception as e:
    print(f"加载CUDA算子失败: {str(e)}")
    print("将使用PyTorch实现代替CUDA算子")
    USE_CUDA_KERNEL = False


class FusedAntiAliasActivation(torch.autograd.Function):
    """
    Assumes filter size 12, replication padding on upsampling/downsampling, and logscale alpha/beta parameters as inputs.
    The hyperparameters are hard-coded in the kernel to maximize speed.
    NOTE: The fused kenrel is incorrect for Activation1d with different hyperparameters.
    """

    @staticmethod
    def forward(ctx, inputs, up_ftr, down_ftr, alpha, beta):
        if not USE_CUDA_KERNEL:
            raise RuntimeError("CUDA算子未加载，无法使用FusedAntiAliasActivation")
        
        activation_results = anti_alias_activation_cuda.forward(
            inputs, up_ftr, down_ftr, alpha, beta
        )

        return activation_results

    @staticmethod
    def backward(ctx, output_grads):
        raise NotImplementedError
        return output_grads, None, None


class Activation1d(nn.Module):
    def __init__(
        self,
        activation,
        up_ratio: int = 2,
        down_ratio: int = 2,
        up_kernel_size: int = 12,
        down_kernel_size: int = 12,
        fused: bool = True,
    ):
        super().__init__()
        self.up_ratio = up_ratio
        self.down_ratio = down_ratio
        self.act = activation
        self.upsample = UpSample1d(up_ratio, up_kernel_size)
        self.downsample = DownSample1d(down_ratio, down_kernel_size)

        # 如果CUDA算子加载失败，强制使用非融合模式
        self.fused = fused and USE_CUDA_KERNEL

    def forward(self, x):
        if not self.fused:
            x = self.upsample(x)
            x = self.act(x)
            x = self.downsample(x)
            return x
        else:
            if self.act.__class__.__name__ == "Snake":
                beta = self.act.alpha.data  # Snake uses same params for alpha and beta
            else:
                beta = (
                    self.act.beta.data
                )  # Snakebeta uses different params for alpha and beta
            alpha = self.act.alpha.data
            if (
                not self.act.alpha_logscale
            ):  # Exp baked into cuda kernel, cancel it out with a log
                alpha = torch.log(alpha)
                beta = torch.log(beta)

            x = FusedAntiAliasActivation.apply(
                x, self.upsample.filter, self.downsample.lowpass.filter, alpha, beta
            )
            return x
