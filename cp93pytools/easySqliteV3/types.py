from typing import Dict, List, Any, Tuple, TypeVar

Data = Any
Record = Dict[str, Data]
Params = List[Data]
DataRow = List[Data]

K = TypeVar('K')
V = TypeVar('V')


def unzip(record: Dict[K, V]) -> Tuple[List[K], List[V]]:
    return map(list, zip(*record.items()))  # type:ignore