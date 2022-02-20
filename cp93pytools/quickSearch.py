from collections import defaultdict
import math
from typing import DefaultDict, List, Sequence, Tuple
import unicodedata
from unidecode import unidecode

NGrams = DefaultDict[str, int]
T_ngrams = DefaultDict[str, List[Tuple[int, int]]]
T_scorer = DefaultDict[int, int]
T_best = DefaultDict[str, T_scorer]


def remove_accents(s: str):
    nfkd_form = unicodedata.normalize('NFKD', s)
    out = u"".join([c for c in nfkd_form if not unicodedata.combining(c)])
    return str(unidecode(out))  # Latinize unknown characters


class quickFilter(List[str]):
    """
  custom fuzzy filter that uses 1,2,3-grams to filter and sort
  several strings by their similarity with a given pattern
  """
    _ngrams: T_ngrams
    _max_score: List[int]
    _each: List[NGrams]
    K = 5

    def __init__(self, elems: Sequence[str], ignore_accents=True,
                 ignore_case=True):
        self[:] = elems

        if ignore_accents and ignore_case:
            self._parser = lambda s: remove_accents(s.lower())
        elif ignore_accents:
            self._parser = lambda s: remove_accents(s)
        elif ignore_case:
            self._parser = lambda s: s.lower()
        else:
            self._parser = lambda s: s

        parsed = [self._parser(s) for s in elems]
        self._each = [self._get_grams(s) for s in parsed]

        best: T_best = defaultdict(lambda: defaultdict(lambda: 0))
        for i in range(len(self)):
            for sub, score in self._each[i].items():
                best[sub][i] = max(best[sub][i], score)

        ngrams: T_ngrams = defaultdict(lambda: [])
        for sub in best:
            for i, score in best[sub].items():
                ngrams[sub].append((i, score))
        self._ngrams = ngrams
        self._max_score = [self._cmp(g, g) for g in self._each]

    @classmethod
    def _get_grams(cls, pattern: str) -> DefaultDict[str, int]:
        '''
        Compute all 1,2,..,K-grams of pattern and their score, possibly repeating.
        The output size is bounded by 3*len(pattern)
        Additional score is given if the gram comes after space, dash or underscore.
        '''
        n = len(pattern)
        out = defaultdict(lambda: 0)
        for i in range(n):
            isStart = (i == 0) or (pattern[i - 1] in (' ', '-', '_', ':'))
            for j in range(i + 1, 1 + min(i + cls.K, n)):
                sub = pattern[i:j]
                score = isStart + len(sub)
                out[sub] += score
        return out

    @classmethod
    def cmp(cls, pattern: str, target: str) -> int:
        src = cls._get_grams(pattern)
        tgt = cls._get_grams(target)
        return cls._cmp(src, tgt)

    @classmethod
    def _cmp(cls, src: NGrams, tgt: NGrams) -> int:
        score = 0
        for sub in set(src) & set(tgt):
            score += src[sub] * tgt[sub]
        return score

    @classmethod
    def wcmp(cls, pattern: str, target: str) -> float:
        'Weighted comparison w.r.t. max score'
        src = cls._get_grams(pattern)
        tgt = cls._get_grams(target)
        AB = cls._cmp(src, tgt)
        AA = cls._cmp(src, src)
        BB = cls._cmp(tgt, tgt)
        return 2 * AB / (AA + BB)

    def cmp_vs_one(self, pattern: str, idx: int) -> int:
        src = self._get_grams(pattern)
        tgt = self._each[idx]
        return self._cmp(src, tgt)

    def wcmp_vs_one(self, pattern: str, idx: int) -> float:
        src = self._get_grams(pattern)
        tgt = self._each[idx]
        AB = self._cmp(src, tgt)
        AA = self._cmp(src, src)
        BB = self._max_score[idx]
        return 2 * AB / (AA + BB)

    def cmp_vs_all(self, pattern: str) -> List[Tuple[int, int]]:
        '''
        Compute the fuzzy match score of pattern vs elements that have at least 1 ngram in common.
        Return the list [(i,score)] sorted by score, highest to lowest.
        '''
        src = self._get_grams(self._parser(pattern))
        scored: T_scorer = defaultdict(lambda: 0)
        for sub, a in src.items():
            for i, b in self._ngrams[sub]:
                scored[i] += a * b
        return sorted(scored.items(), key=(lambda t: (-t[1], t[0])))

    def wcmp_vs_all(self, pattern: str) -> List[Tuple[int, float]]:
        src = self._get_grams(self._parser(pattern))
        score: DefaultDict[int, float] = defaultdict(lambda: 0)
        for sub, a in src.items():
            for i, b in self._ngrams[sub]:
                score[i] += a * b
        AA = self._cmp(src, src)
        for i in score:
            AB = score[i]
            BB = self._max_score[i]
            score[i] = 2 * AB / (AA + BB)
        return sorted(score.items(), key=(lambda t: (-t[1], t[0])))

    def rank(self, pattern: str) -> List[Tuple[str, float]]:
        ranking = [(self[i], score) for i, score in self.wcmp_vs_all(pattern)]
        if len(ranking) == 0:
            ranking: List[Tuple[str, float]] = [('', 0)]
        return ranking
