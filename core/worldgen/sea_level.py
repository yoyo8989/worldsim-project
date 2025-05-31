"""
sea_level.py

海面変動シミュレーションモジュール。
- 年代に応じた海面高さを計算
- DEM を水没・露出判定して更新
- デフォルトまたはカスタムのシナリオ曲線を適用可能
- NumPy マスキングによる高速処理
"""

import logging
from functools import lru_cache
from typing import Optional, Callable, Union, Dict

import numpy as np

# モジュールレベルロガーの初期化
def _get_logger() -> logging.Logger:
    logger = logging.getLogger(__name__)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('[%(levelname)s] %(name)s: %(message)s'))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger

logger = _get_logger()

# デフォルト海面変動関数
@lru_cache(maxsize=1)
def _default_curve(year: int) -> float:
    """
    線形かつ上限付き: 0年→0m, 1000年→100m、それ以上は100mに飽和
    """
    clamped = min(max(year, 0), 1000)
    return clamped * 0.1

# シナリオ曲線のレジストリ\ _CURVE_REGISTRY: Dict[str, Callable[[int], float]] = {
    'default': _default_curve,
}

@lru_cache(maxsize=10)
def _resolve_curve(
    curve: Union[str, Callable[[int], float]]
) -> Callable[[int], float]:
    """
    指定された曲線を解決します。

    - 文字列: レジストリから取得、未登録時は例外
    - 関数: そのまま返却
    """
    if callable(curve):
        return curve
    if curve in _CURVE_REGISTRY:
        return _CURVE_REGISTRY[curve]
    logger.error("Unknown sea level curve: %s", curve)
    raise ValueError(f"Unknown sea level curve: {curve}")


def apply_sea_level(
    dem: np.ndarray,
    year: int,
    curve: Optional[Union[str, Callable[[int], float]]] = None
) -> np.ndarray:
    """
    DEM に海面変動を適用し、水没セルを NaN でマスクして返却します。

    Args:
        dem: 2D numpy 配列の高度マップ
        year: シミュレーション年（非負整数）
        curve: 'default' または年→高さ関数

    Returns:
        新しい高度マップ（浮力部が NaN）

    Raises:
        ValueError: dem の次元不正、year が負、曲線指定エラー
    """
    # 入力検証
    if not isinstance(dem, np.ndarray) or dem.ndim != 2:
        logger.error("Invalid dem: expected 2D numpy array, got %r", dem.shape if hasattr(dem, 'shape') else type(dem))
        raise ValueError("dem must be a 2D numpy array")
    if not isinstance(year, int) or year < 0:
        logger.error("Invalid year: expected non-negative integer, got %r", year)
        raise ValueError("year must be a non-negative integer")

    # 曲線取得
    fn = _resolve_curve(curve or 'default')

    # 海面高さ計算
    sea_level = fn(year)
    logger.info("Sea level at year %d: %.2f m", year, sea_level)

    # DEM を float に変換してマスク
    result = dem.astype(float)
    mask = result <= sea_level
    result[mask] = np.nan

    return result
