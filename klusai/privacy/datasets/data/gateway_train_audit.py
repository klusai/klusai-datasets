"""Cross-split MinHash and exact Jaccard audit, including PII-masked templates.

MinHash LSH accelerates candidate discovery. A complete prefix-filter join at the same
Jaccard threshold certifies that LSH misses cannot be mistaken for zero overlap.
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import Counter, defaultdict

import numpy as np

THRESHOLD = 0.8
PERMUTATIONS = 128
SEED = 12703
SHINGLE_WORDS = 5


def skeleton(row):
    text = row["text"]
    for span in sorted(row["spans"], key=lambda s: s["start"], reverse=True):
        text = text[: span["start"]] + " " + span["label"] + " " + text[span["end"] :]
    return text


def shingles(text, masked=False):
    words = re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold())
    if masked:
        # Numeric task parameters must not disguise a reused template.
        words = [re.sub(r"\d+", "0", word) for word in words]
    if len(words) < SHINGLE_WORDS:
        return frozenset({" ".join(words)})
    return frozenset(" ".join(words[i : i + SHINGLE_WORDS]) for i in range(len(words) - SHINGLE_WORDS + 1))


def jaccard(a, b):
    return len(a & b) / len(a | b) if a or b else 1.0


class SimilarityIndex:
    def __init__(self, documents, threshold=THRESHOLD):
        self.threshold = threshold
        self.documents = list(dict.fromkeys(documents))
        if not self.documents:
            raise ValueError("Cannot audit against an empty heldout index")
        rng = np.random.default_rng(SEED)
        self.a = rng.integers(1, 2**32, PERMUTATIONS, dtype=np.uint64)
        self.b = rng.integers(0, 2**32, PERMUTATIONS, dtype=np.uint64)
        self.prime = np.uint64(2**61 - 1)
        self.lsh = defaultdict(set)
        self.prefixes = defaultdict(set)
        self.frequency = Counter(token for doc in self.documents for token in doc)
        self.signatures = []
        self.cache = {}
        for index, doc in enumerate(self.documents):
            signature = self.signature(doc)
            self.signatures.append(signature)
            for band, key in enumerate(signature.reshape(32, 4)):
                self.lsh[(band, key.tobytes())].add(index)
            for token in self.prefix(doc):
                self.prefixes[token].add(index)

    def prefix(self, doc):
        # Fixed global order, including unseen train-only tokens (frequency zero).
        ordered = sorted(doc, key=lambda token: (self.frequency[token], token))
        return ordered[: len(doc) - math.ceil(self.threshold * len(doc)) + 1]

    def signature(self, doc):
        hashed = np.array(
            [int.from_bytes(hashlib.sha256(s.encode()).digest()[:4], "little") for s in doc], dtype=np.uint64
        )
        return ((hashed[:, None] * self.a + self.b) % self.prime).min(axis=0)

    def query(self, doc):
        if doc in self.cache:
            return self.cache[doc]
        signature = self.signature(doc)
        candidates = set()
        lsh = set()
        for band, key in enumerate(signature.reshape(32, 4)):
            lsh.update(self.lsh.get((band, key.tobytes()), ()))
        for token in self.prefix(doc):
            candidates.update(self.prefixes.get(token, ()))
        candidates.update(lsh)
        candidates = {
            i for i in candidates if self.threshold * len(doc) <= len(self.documents[i]) <= len(doc) / self.threshold
        }
        matches = [
            (i, jaccard(doc, self.documents[i]))
            for i in candidates
            if jaccard(doc, self.documents[i]) >= self.threshold
        ]
        result = dict(
            matches=matches,
            minhash_candidates=len(lsh),
            exact_candidates=len(candidates),
            minhash_estimate_max=max(
                (float(np.mean(signature == self.signatures[i])) for i in candidates), default=0.0
            ),
        )
        self.cache[doc] = result
        return result
