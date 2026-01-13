import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi


class HybridSearcher:
    """BM25 + (옵션) Chroma Dense 검색을 결합한 하이브리드 검색기.

    ⚠ 중요:
    - Chroma(HNSW) 인덱스가 깨져 있을 수 있으므로,
      collection.query() 호출은 try/except로 감싸 안전하게 처리한다.
    - Chroma 쿼리가 실패하면 BM25 단독으로라도 결과를 반환한다.
    """

    def __init__(self, df: pd.DataFrame, chroma_collection):
        self.df = df
        self.collection = chroma_collection

        # --- BM25 준비 ---
        corpus = df["desc"].astype(str).tolist()
        tokenized_corpus = [doc.lower().split() for doc in corpus]
        self.bm25 = BM25Okapi(tokenized_corpus)

    def _bm25_search(self, query: str, top_k: int = 5):
        """BM25 결과를 score + row 형태로 반환."""
        tokens = query.lower().split()
        scores = self.bm25.get_scores(tokens)

        # 상위 top_k 인덱스 선택
        top_indices = np.argsort(-scores)[:top_k]

        results = []
        for idx in top_indices:
            score = float(scores[idx])
            row = self.df.iloc[int(idx)]
            results.append({"score": score, "row": row})
        return results

    def _dense_search_safe(self, query: str, top_k: int = 5):
        """Chroma dense 검색. 실패하면 빈 리스트 반환 (BM25만 사용)."""
        if self.collection is None:
            return []

        try:
            dense_results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
            )
        except Exception as e:
            # HNSW 인덱스 깨짐 등으로 실패할 수 있음 → 조용히 무시하고 BM25만 사용
            # 필요하면 print(e)로 디버깅
            # print(f"[HybridSearcher] Dense search failed: {e}")
            return []

        if not dense_results or not dense_results.get("documents"):
            return []

        dense_hits = []
        docs = dense_results.get("documents", [[]])[0]
        distances = dense_results.get("distances", [[]])[0]
        ids = dense_results.get("ids", [[]])[0]

        for i in range(len(docs)):
            try:
                row_idx = int(ids[i])
                row = self.df.iloc[row_idx]
            except Exception:
                # id를 인덱스로 해석하지 못하면 건너뜀
                continue

            # Chroma의 distance는 '거리'이므로, 음수로 바꿔서 BM25와 방향 맞춰줌
            score = -float(distances[i])
            dense_hits.append({"score": score, "row": row})

        return dense_hits

    def search(self, query: str, top_k: int = 5):
        """하이브리드 검색.

        1) BM25로 전 범위 검색
        2) 가능하면 Chroma dense 검색 추가
        3) 두 결과를 score 기준으로 합쳐 상위 top_k만 반환
        """
        # 1) BM25
        bm25_results = self._bm25_search(query, top_k=top_k)

        # 2) Dense (안전모드)
        dense_hits = self._dense_search_safe(query, top_k=top_k)

        # 3) 결합
        combined = bm25_results + dense_hits
        if not combined:
            return []

        combined = sorted(combined, key=lambda x: -x["score"])
        return combined[:top_k]
