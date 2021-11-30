from __future__ import annotations
from typing import List, Optional, Tuple
import abc
from .types import (Params, Data, unzip)


class _Str(abc.ABC):

    @abc.abstractmethod
    def _str(self, params: Params) -> str:
        ...


class Where(_Str):
    pass


class RawWhere(Where):

    def __init__(self, query: str, *params: Data):
        self.query = query
        self.params = params

    def _str(self, params: Params):
        params.extend(self.params)
        return self.query


class WhereAnd(Where):

    def __init__(self, first: Where, second: Where):
        self.first = first
        self.second = second

    def _str(self, params: Params):
        first = self.first._str(params)
        second = self.second._str(params)
        return f'({first}) AND {second}'


class WhereEqual(RawWhere):
    '''
    Particular case of Where:
        key1 = value1 AND key2 = value2 AND ...
    Implemented separately for speed because it is very common 
    '''

    def __init__(self, **kwargs: Data):
        keys, values = unzip(kwargs)
        query = ' AND '.join(f'{k} = ?' for k in keys)
        super().__init__(query, *values)
        # save also kwargs (only for update query):
        self.kwargs = kwargs


class Everywhere(Where):

    def _str(self, params: Params):
        return ''


everywhere = Everywhere()  # Constant

EverywhereError = 'To prevent an accident, you must specify .where(..) for delete/update queries. If you really want everywhere use .everywhere()'


class QueryBody(_Str):

    _where: Optional[Where] = None
    _order_by: Tuple[str, ...] = ()
    _limit: Optional[int] = None

    def _str(self, params: List[Data]):
        body = []
        if self._where is not None:
            where_str = self._where._str(params)
            body.append(f'WHERE {where_str}')
        if self._order_by:
            by = ', '.join(self._order_by)
            body.append(f'ORDER BY {by}')
        if self._limit is not None:
            body.append('LIMIT ?')
            params.append(int(self._limit))
        return ' '.join(body)
