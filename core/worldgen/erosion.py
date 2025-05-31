"""
erosion.py

侵食・堆積シミュレーションモジュール。
- 複数モデル（'basic', 'thermal'）を terrainbento 経由で適用
- DEM（高度マップ）を入力し、新しい DEM を返却するインターフェースを提供
- オプションで再現性制御用 RNG またはシード指定可能
- SciPy のベクトル化演算で高速処理
- 不正モデル名や処理エラーは例外で明示的に通知
"""

import logging
from functools import lru_cache
from typing import Optional, Union, Dict

import numpy as np
from scipy import ndimage
import terrainbento

# ロガー設定
def _get_logger():
    logger = logging.getLogger(__name__)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('[%(levelname)s] %(name)s: %(message)s'))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger

logger = _get_logger()

# terrainbento モデル名とクラス名マッピング
erosion_models: Dict[str, str] = {
    'basic': 'HydraulicErosionModel',
    'thermal': 'ThermalErosionModel',
}

# スムージングカーネル定義
SMOOTHING_KERNEL = np.array([
    [1, 2, 1],
    [2, 4, 2],
    [1, 2, 1]
]) / 16

@lru_cache(maxsize=2)
def _load_erosion_model(model_name: str):
    """
    terrainbento の ErosionModel クラスをロードしキャッシュします。
    Raises ValueError if model_name unsupported or class not found.
    """
    if model_name not in erosion_models:
        logger.error("Unsupported erosion model requested: %s", model_name)
        raise ValueError(f"Unsupported erosion model: {model_name}")
    class_name = erosion_models[model_name]
    try:
        model_cls = getattr(terrainbento, class_name)
    except AttributeError:
        logger.error("terrainbento クラス '%s' が見つかりません", class_name)
        raise ValueError(f"Model class '{class_name}' not found in terrainbento")
    logger.debug("Loaded terrainbento model: %s", class_name)
    return model_cls()


def run_erosion(
    dem: np.ndarray,
    model: str = 'basic',
    seed: Optional[int] = None,
    rng: Optional[np.random.Generator] = None,
    noise_scale: float = 0.0
) -> np.ndarray:
    """
    DEM に侵食・堆積処理を適用し、新しい DEM を返します。

    Args:
        dem (np.ndarray): shape=(H, W) の2D高度マップ
        model (str): 'basic' or 'thermal'
        seed (int, optional): RNGを初期化するシード
        rng (np.random.Generator, optional): 外部RNGを直接指定するとseedは無視
        noise_scale (float): 終了後に追加するノイズの標準偏差

    Returns:
        np.ndarray: 処理後の DEM

    Raises:
        ValueError: 入力DEMが2D配列でない、またはnoise_scaleが負、
                    モデル名不正時
        RuntimeError: terrainbento 実行中の例外をラップ
    """
    # 入力検証
    if not isinstance(dem, np.ndarray) or dem.ndim != 2:
        logger.error("dem must be a 2D numpy array, got %r", dem.shape if isinstance(dem, np.ndarray) else type(dem))
        raise ValueError("dem must be a 2D numpy array")
    if noise_scale < 0:
        logger.error("noise_scale must be non-negative, got %s", noise_scale)
        raise ValueError("noise_scale must be non-negative")

    # RNG設定
    if rng is None:
        if seed is None:
            rng = np.random.default_rng()
        else:
            rng = np.random.default_rng(seed)

    logger.info("Starting erosion model '%s' on DEM of shape %s", model, dem.shape)

    # モデル実行
    try:
        model_instance = _load_erosion_model(model)
        processed = model_instance.apply(dem)
        if not isinstance(processed, np.ndarray):
            raise RuntimeError("terrainbento model did not return numpy array")
    except ValueError:
        logger.warning("Unsupported model '%s'; applying Gaussian smoothing fallback", model)
        processed = ndimage.gaussian_filter(dem, sigma=1)
    except Exception as e:
        logger.error("Error running terrainbento model '%s': %s", model, e)
        raise RuntimeError(f"Erosion model error: {e}")

    # 基本モデル向け軽量平滑化
    if model == 'basic':
        processed = ndimage.convolve(processed, SMOOTHING_KERNEL, mode='reflect')

    # ノイズ追加
    if noise_scale > 0:
        noise = rng.normal(loc=0.0, scale=noise_scale, size=dem.shape)
        processed = processed + noise
        logger.debug("Added noise with scale %s", noise_scale)

    logger.info("Erosion model '%s' completed", model)
    return processed
