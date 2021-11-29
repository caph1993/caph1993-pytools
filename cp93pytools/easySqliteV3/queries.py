from __future__ import annotations
from typing import TYPE_CHECKING, Callable, Dict, List, Any, Optional, Tuple, TypeVar, cast
from functools import wraps
from random import shuffle
import abc
from .types import (
    DataRow,
    Params,
    Data,
    Record,
)
if TYPE_CHECKING:
    from .table import SqliteTable


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


EverywhereError = 'To prevent an accident, you must specify .where(..) for delete/update queries. If you really want everywhere use .raw_where("1=1")'


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


F = TypeVar('F', bound=Callable)


def query_method(wrapped: F) -> F:
    '''
    Decorator for using Query methods from
    classes that inherit from it
    '''

    @wraps(wrapped)
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, 'body'):
            self = Query(self, QueryBody())
        return wrapped(self, *args, **kwargs)

    return cast(F, wrapper)


K = TypeVar('K')
V = TypeVar('V')


def unzip(record: Dict[K, V]) -> Tuple[List[K], List[V]]:
    return map(list, zip(*record.items()))  # type:ignore


class Query:

    body: QueryBody

    def __init__(self, table: SqliteTable, body: QueryBody):
        self.table_name = table.name
        self.db = table.db
        self.body = body

    # "Where" related methods

    @query_method
    def where(self, **key_values):
        self.body._where = WhereEqual(**key_values)
        return self

    @query_method
    def raw_where(self, query: str, *params: Any):
        self.body._where = RawWhere(query, *params)
        return self

    @query_method
    def order_by(self, *columns_asc_desc: str):
        self.body._order_by = columns_asc_desc
        return self

    @query_method
    def limit(self, limit: Optional[int]):
        self.body._limit = limit
        return self

    # Select method and mutation methods

    @query_method
    def select(self, *columns: str):
        what = ', '.join(columns) or '*'
        params = []
        where = self.body._str(params)
        query = (f'SELECT {what}' f' FROM {self.table_name} {where}')
        return self.db._execute(query, params)

    @query_method
    def delete(self):
        assert self.body._where is not None, EverywhereError
        params = []
        where = self.body._str(params)
        query = f'DELETE FROM {self.table_name} {where}'
        return self.db._execute(query, params)

    @query_method
    def insert(self, **record: Data):
        #inst = 'INSERT OR IGNORE' if ignore else 'INSERT'
        where = self.body._str([]).strip()
        assert not where, f'Unexpected statements for INSERT: {where}'
        table = self.table_name
        keys, values = unzip(record)
        columns = ', '.join(keys)
        marks = ', '.join('?' for _ in keys)
        query = f'INSERT INTO {table} ({columns}) VALUES ({marks})'
        return self.db._execute(query, values)

    @query_method
    def insert_or_ignore(self, **record: Data):
        where = self.body._str([]).strip()
        assert not where, f'Unexpected statements for INSERT: {where}'
        table = self.table_name
        keys, values = unzip(record)
        columns = ', '.join(keys)
        marks = ', '.join('?' for _ in keys)
        query = f'INSERT OR IGNORE INTO {table} ({columns}) VALUES ({marks})'
        cursor = self.db._execute(query, values)
        return cursor.rowcount

    @query_method
    def update_or_ignore(self, **partial_record: Data):
        assert self.body._where is not None, EverywhereError
        keys, params = unzip(partial_record)
        what = ', '.join(f'{c} = ?' for c in keys)
        where = self.body._str(params)
        query = f'UPDATE {self.table_name} SET {what} {where}'
        cursor = self.db._execute(query, params)
        return cursor.rowcount

    @query_method
    def update(self, **partial_record: Data):
        if not self.update_or_ignore(**partial_record):
            self.insert(**partial_record)
        return

    @query_method
    def count(self):
        return int(self.value('count(*)'))

    # high-level select methods

    @query_method
    def rows(self, *columns: str) -> List[DataRow]:
        return [*self.select(*columns)]

    @query_method
    def dicts(self, *columns: str) -> List[Record]:
        cursor = self.select(*columns)
        names = [c for c, *_ in cursor.description]
        return [dict(zip(names, row)) for row in cursor]

    @query_method
    def column(self, column: str) -> List[Data]:
        return [first for first, *_ in self.rows(column)]

    @query_method
    def value(self, column: str) -> Data:
        return self.limit(1).column(column)[0]

    @query_method
    def dict(self, *columns: str) -> Record:
        return self.limit(1).dicts(*columns)[0]

    @query_method
    def get_value(self, column: str) -> Optional[Data]:
        col = self.limit(1).column(column)
        return col[0] if col else None

    @query_method
    def get_dict(self, *columns: str) -> Optional[Record]:
        dicts = self.limit(1).dicts(*columns)
        return dicts[0] if dicts else None

    @query_method
    def series(self, *columns: str) -> Dict[str, List[Data]]:
        cursor = self.select(*columns)
        keys = [x[0] for x in cursor.description]
        out = {key: [] for key in keys}
        for row in cursor:
            for key, value in zip(keys, row):
                out[key].append(value)
        return out

    # random selection methods

    @query_method
    def random_rows(self, n: int, *columns: str):
        rows, _ = self._select_random(n, *columns)
        return rows

    @query_method
    def random_dicts(self, n: int, *columns: str) -> List[Record]:
        rows, keys = self._select_random(n, *columns)
        return [dict(zip(keys, row)) for row in rows]

    @query_method
    def random_dict(self, *columns: str):
        return self.random_dicts(1, *columns)[0]

    @query_method
    def _select_random(self, n: int, *columns: str):
        assert n > 0, 'Empty selection unsupported'
        N: int = self.count()
        assert N > 0, 'The table is empty'
        where = self.body._where
        column_names = []
        rows: List[List[Data]] = []
        while len(rows) < n:
            remaining = n - len(rows)
            # Filter many out randomly
            mod = 1 + N // (2 * remaining)
            print(mod)
            new_where = RawWhere(f'random() % ? = 0', mod)
            if where is not None:
                new_where = WhereAnd(where, new_where)
            self.body._order_by = ()
            self.body._where = new_where
            cursor = self.limit(remaining).select(*columns)
            column_names = [x[0] for x in cursor.description]
            rows.extend(cursor)
        shuffle(rows)
        return rows, column_names
