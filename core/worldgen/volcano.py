"""
volcano.py

火山活動・クレーター生成モジュール。
- cratermaker ライブラリを利用してクレーターを生成
- rate (0.0-1.0) に応じた確率的噴火・クレーター埋め込み
- DEM を入力し、新しい DEM を返却するインターフェースを提供
- vectorized フォールバックロジックを含む
"""

import logging
from functools import lru_cache
from typing import Optional

import numpy as np
import cratermaker


def _get_logger() -> logging.Logger:
    """
    モジュールレベルのロガーを設定します。
    """
    logger = logging.getLogger(__name__)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('[%(levelname)s] %(name)s: %(message)s'))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger

logger = _get_logger()

@lru_cache(maxsize=1)
def _init_crater_maker(width: int, height: int) -> cratermaker.CraterMaker:
    """
    cratermaker.CraterMaker インスタンスを初期化してキャッシュします。
    """
    logger.debug("Initializing CraterMaker with size %dx%d", width, height)
    try:
        return cratermaker.CraterMaker(width=width, height=height)
    except Exception as e:
        logger.error("Failed to initialize CraterMaker: %s", e)
        raise


def generate_volcanoes(
    dem: np.ndarray,
    rate: float,
    seed: Optional[int] = None,
    rng: Optional[np.random.Generator] = None
) -> np.ndarray:
    """
    DEM に火山クレーターをランダム生成して新しい DEM を返します。

    Args:
        dem (np.ndarray): 2D 高度マップ
        rate (float): クレーター発生率 (0.0～1.0)
        seed (int, optional): rng 未指定時に使用する乱数シード
        rng (np.random.Generator, optional): 外部乱数ジェネレータを指定

    Returns:
        np.ndarray: クレーター適用後の高度マップ

    Raises:
        ValueError: 入力パラメータが不正な場合
        RuntimeError: cratermaker 実行中に致命的エラーが発生した場合
    """
    # 入力検証
    if not isinstance(dem, np.ndarray) or dem.ndim != 2:
        logger.error("Invalid dem: expected 2D numpy array, got %r", dem.shape if hasattr(dem, 'shape') else type(dem))
        raise ValueError("dem must be a 2D numpy array")
    if not 0.0 <= rate <= 1.0:
        logger.error("Invalid rate: must be between 0.0 and 1.0, got %s", rate)
        raise ValueError("rate must be between 0.0 and 1.0")

    # RNG 設定
    if rng is None:
        rng = np.random.default_rng(seed)

    h, w = dem.shape
    total = h * w
    num_craters = int(total * rate)
    logger.info("Generating %d craters on DEM shape %s (rate=%.3f)", num_craters, dem.shape, rate)

    # クレーター生成: 通常処理
    try:
        maker = _init_crater_maker(w, h)
        new_dem = maker.generate_craters(dem=dem, num_craters=num_craters)
        if not isinstance(new_dem, np.ndarray):
            raise RuntimeError("generate_craters did not return numpy array")
    except Exception as e:
        logger.warning("CraterMaker failed (%s), using vectorized fallback", e)
        # vectorized fallback: flatten 処理で大量データにも高速適用
        flat = dem.ravel().copy()
        indices = rng.choice(total, size=num_craters, replace=False)
        depths = rng.uniform(0.1, 1.0, size=num_craters)
        flat[indices] -= depths
        new_dem = flat.reshape(h, w)

    logger.info("Crater generation completed")
    return new_dem