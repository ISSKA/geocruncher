from abc import ABC, abstractmethod
from pathlib import Path
import json
from typing import Dict, Any
import redis


class ProfilerStorage(ABC):
    """Abstract base class for profiler storage backends"""

    @abstractmethod
    def save(self, computation: str, version: int, metadata: Dict[str, Any], steps: Dict[str, Dict[str, float]]) -> None:
        pass


class CSVStorage(ProfilerStorage):
    """CSV file storage for profiler results"""

    def __init__(self, output_folder: Path):
        self.output_folder = output_folder

    def save(self, computation: str, version: int, metadata: Dict[str, Any], steps: Dict[str, Dict[str, float]]) -> None:
        file_name = f"{computation}_v{version}.csv"
        file_path = self.output_folder / file_name

        separator = ';'
        header = self._get_csv_header(metadata.keys(), steps.keys(), separator)
        line = self._get_csv_line(metadata, steps, separator)

        with open(file_path, "a+", encoding="utf8") as f:
            f.seek(0)
            if len(f.read()) == 0:
                f.write(header)
            f.write(line)

    def _get_csv_header(self, metadata_keys, step_keys, separator=';'):
        return separator.join(metadata_keys) + separator + separator.join(step_keys) + '\n'

    def _get_csv_line(self, metadata: dict, steps: dict, separator=';'):
        metadata_values = separator.join(str(x) for x in metadata.values())
        step_values = separator.join(
            self._s_to_ms(x['time']) for x in steps.values())
        return metadata_values + separator + step_values + '\n'

    def _s_to_ms(self, s: float) -> str:
        return f'{s * 1000:.5f}'


class RedisStorage(ProfilerStorage):
    """Redis storage for profiler results"""

    def __init__(self, host: str, port: int = 6379, db: int = 3):
        self.client = redis.StrictRedis(host=host, port=port, db=db)

    def save(self, computation: str, version: int, metadata: Dict[str, Any], steps: Dict[str, Dict[str, float]]) -> None:
        key = f"profiling:{computation}:v{version}"

        profiler_data = {
            'metadata': metadata,
            'steps': {step: {'time_ms': round(step_data['time'] * 1000, 5)}
                      for step, step_data in steps.items()}
        }

        json_data = json.dumps(profiler_data, separators=(',', ':'))
        self.client.rpush(key, json_data)
