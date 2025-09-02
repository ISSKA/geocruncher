import os
from pathlib import Path
from typing import Optional
from .storage import ProfilerStorage, CSVStorage, RedisStorage


class ProfilerConfig:
    """Configuration for the profiler system"""

    def __init__(self):
        self.is_enabled = os.environ.get('PROFILING_ENABLED', 'false').lower() == 'true'
        self.storage_type = os.environ.get('PROFILER_STORAGE_TYPE', 'redis').lower()
        self.output_folder = Path(os.environ.get('PROFILER_OUTPUT_FOLDER', Path.cwd()))
        self.redis_host = os.environ.get('REDIS_HOST', 'localhost')
        self.redis_port = int(os.environ.get('REDIS_PORT', '6379'))
        # Per default this uses db 3 because db 0, 1 and 2 are already
        # getting used by geocruncher/celery.
        self.redis_db = int(os.environ.get('REDIS_DB', '3'))

    def create_storage(self) -> Optional[ProfilerStorage]:
        """Create storage backend based on configuration"""
        if not self.is_enabled:
            return None

        if self.storage_type == 'csv':
            return CSVStorage(self.output_folder)
        elif self.storage_type == 'redis':
            return RedisStorage(self.redis_host, self.redis_port, self.redis_db)
        else:
            raise ValueError(f"Unknown storage type: {self.storage_type}")
