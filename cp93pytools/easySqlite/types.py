from typing import Dict, List, Tuple, TypeVar, Union

Data = Union[str, float, int, bool, None]
Record = Dict[str, Data]
Params = List[Data]
DataRow = List[Data]

K = TypeVar('K')
V = TypeVar('V')


def unzip(record: Dict[K, V]) -> Tuple[List[K], List[V]]:
    return map(list, zip(*record.items()))  # type:ignore
