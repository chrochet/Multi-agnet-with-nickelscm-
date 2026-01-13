# 관세율2/modules/chroma_builder.py
# ✅ default_tenant 오류 자동 복구 + build_chroma 유지 버전 (전체 교체용)

import uuid
import shutil
from pathlib import Path

from chromadb import PersistentClient
from chromadb.config import Settings

from modules.utils import get_project_root
from modules.data_loader import load_tariff_data

COLLECTION_NAME = "tariff_metals"


def _db_path() -> Path:
    p = get_project_root() / "db" / "chroma"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_chroma_client() -> PersistentClient:
    """
    PersistentClient 생성.
    - default_tenant/tenant 오류(로컬 DB 손상/버전 꼬임) 나면
      db/chroma 폴더 삭제 후 재생성해서 자동 복구.
    ※ Streamlit cache_resource 쓰지 않음(깨진 객체 캐싱 방지)
    """
    db_path = _db_path()
    settings = Settings(anonymized_telemetry=False, allow_reset=True)

    try:
        return PersistentClient(path=str(db_path), settings=settings)
    except Exception:
        # 깨진 DB 제거 후 재생성
        shutil.rmtree(db_path, ignore_errors=True)
        db_path.mkdir(parents=True, exist_ok=True)
        return PersistentClient(path=str(db_path), settings=settings)


def _row_to_document(row) -> str:
    return (
        f"Country: {row.get('country','')} | "
        f"HS: {row.get('hs_code','')} | "
        f"Description: {row.get('desc','')} | "
        f"MFN rate: {row.get('mfn_rate','')}"
    )


def build_chroma(force_rebuild: bool = False) -> bool:
    """
    CSV 로드 -> 컬렉션 생성/재생성 -> 문서 추가
    """
    client = get_chroma_client()

    if force_rebuild:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    df = load_tariff_data()
    if df is None or df.empty:
        return False

    documents, metadatas, ids = [], [], []
    for _, row in df.iterrows():
        documents.append(_row_to_document(row))
        metadatas.append(
            {
                "country": str(row.get("country", "")),
                "hs_code": str(row.get("hs_code", "")),
                "desc": str(row.get("desc", "")),
                "mfn_rate": str(row.get("mfn_rate", "")),
                "hs2": str(row.get("hs2", "")),
            }
        )
        ids.append(str(uuid.uuid4()))

    # 배치 add
    batch_size = 500
    for i in range(0, len(documents), batch_size):
        j = i + batch_size
        collection.add(
            documents=documents[i:j],
            metadatas=metadatas[i:j],
            ids=ids[i:j],
        )

    return True


def get_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
