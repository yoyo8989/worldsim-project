"""
tectonics.py

プレートテクトニクスモデルを扱うモジュール。
- 乱数シードまたは外部 RNG からプレート境界データを生成
- 各プレートの移動ベクトルを計算
- 高度マップへの反映用インターフェースを提供
- 大量データ処理を非同期化対応
"""

import logging
import asyncio
from functools import lru_cache, partial
from pathlib import Path
import numpy as np
import pygplates
from typing import Optional, Union
from concurrent.futures import ThreadPoolExecutor

# モジュールレベルのロガー設定
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[%(levelname)s] %(name)s: %(message)s'))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# バックグラウンド実行用スレッドプール
_executor = ThreadPoolExecutor(max_workers=2)

@lru_cache(maxsize=1)
def _load_plate_boundaries(path: Path) -> pygplates.FeatureCollection:
    """
    GPMLファイルからプレート境界データをロードし、結果をキャッシュします。
    """
    logger.debug("Loading plate boundaries from %s", path)
    try:
        return pygplates.FeatureCollection(str(path))
    except Exception as e:
        logger.error("Failed to load plate boundaries: %s", e)
        raise


def _sync_generate(
    seed: Optional[int],
    grid_size: int,
    plate_path: Path,
    noise_scale: float,
    rng: np.random.Generator
) -> np.ndarray:
    """
    同期版：プレート境界変形マップを生成します。
    """
    # 変形マップ初期化
    modifier = np.zeros((grid_size, grid_size), dtype=float)

    # TODO: pygplates フィーチャをグリッドにマッピングして影響量を計算

    if noise_scale > 0:
        logger.debug("Applying placeholder noise (scale=%s)", noise_scale)
        modifier += rng.normal(loc=0.0, scale=noise_scale, size=modifier.shape)

    logger.debug("Plate boundary modifier generated successfully")
    return modifier

async def generate_plate_boundaries(
    seed: Optional[int] = None,
    grid_size: int = 100,
    boundary_model_path: Optional[Union[str, Path]] = None,
    noise_scale: float = 0.1,
    rng: Optional[np.random.Generator] = None
) -> np.ndarray:
    """
    非同期版：プレート境界データに基づく変形マップを生成します。

    Args:
        seed (int, optional): 乱数シード（rng 未指定時に利用）
        grid_size (int): 出力グリッドのサイズ
        boundary_model_path (str|Path, optional): GPMLファイルのパス
        noise_scale (float): デバッグ用ノイズ強度
        rng (np.random.Generator, optional): 外部 RNG を指定

    Returns:
        np.ndarray: shape=(grid_size, grid_size) の変形マップ

    Raises:
        FileNotFoundError: プレート境界ファイルが存在しない場合
        ValueError: パラメータが不正な場合
    """
    # バリデーション
    if grid_size <= 0:
        raise ValueError("grid_size must be positive")
    if noise_scale < 0:
        raise ValueError("noise_scale must be non-negative")
    if rng is None:
        if seed is None:
            raise ValueError("Either seed or rng must be provided")
        rng = np.random.default_rng(seed)

    # プレート境界ファイルパス
    default_path = Path(__file__).parent / "data" / "plate_boundaries.gpml"
    plate_path = Path(boundary_model_path) if boundary_model_path else default_path

    # ファイル存在確認とエラー通知
    if not plate_path.is_file():
        logger.error("Plate boundary file not found at %s", plate_path)
        raise FileNotFoundError(f"Plate boundary file not found at {plate_path}")

    # キャッシュ付きロード
    feature_collection = _load_plate_boundaries(plate_path)

    # 同期版実行をスレッドプール経由で呼び出し
    func = partial(_sync_generate, seed, grid_size, plate_path, noise_scale, rng)
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(_executor, func)
    return result