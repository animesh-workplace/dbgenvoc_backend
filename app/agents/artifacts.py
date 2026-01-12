import uuid
import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional


class ArtifactService:
    def __init__(self, storage_path: str = "./artifacts"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self.metadata_db = {}  # In production, use SQLite/Postgres

    def save_artifact(self, data: Any, filename: str, metadata: Dict) -> str:
        artifact_id = f"{filename}_{uuid.uuid4().hex[:8]}"
        # Store full data
        with open(self.storage_path / f"{artifact_id}.json", "w") as f:
            json.dump(data, f)

        # Store metadata
        self.metadata_db[artifact_id] = {
            "filename": filename,
            "created_at": datetime.now().isoformat(),
            "size": len(json.dumps(data)),
            "preview": data[:5] if isinstance(data, list) else str(data)[:200],
            **metadata,
        }
        return artifact_id

    def load_artifact(self, artifact_id: str) -> Optional[Any]:
        try:
            with open(self.storage_path / f"{artifact_id}.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return None

    def get_metadata(self, artifact_id: str) -> Optional[Dict]:
        return self.metadata_db.get(artifact_id)
