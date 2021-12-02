from __future__ import annotations
from typing import Callable, Dict, Iterator, List, Any, Optional, Type, TypeVar, cast
from functools import wraps
from random import shuffle
from . import query_body as QB
from .types import (DataRow, Data, Record, unzip)
from .database import SqliteDB

F = TypeVar('F', bound=Callable)


def query_method(wrapped: F) -> F:
    '''
    Decorator for using TableQuery methods
    from classes that inherit from it.
    When called from a parent, self is converted
    into a new TableQuery with a new empty _body.
    '''

    @wraps(wrapped)
    def wrapper(self: TableQuery, *args, **kwargs):
        if not hasattr(self, '_body'):
            self = TableQuery.new(self)
        return wrapped(self, *args, **kwargs)

    return cast(F, wrapper)


class TableQuery:

    # Abstract attributes (defined by parents):
    db: SqliteDB
    name: str  # table name

    # Non-abstract:
    _body: QB.QueryBody

    @classmethod
    def new(cls, parent: TableQuery):
        query = cls()
        query._body = QB.QueryBody()
        query.db = parent.db
        query.name = parent.name
        return query

    # "Where" related methods

    @query_method
    def where(self, **key_values):
        self._body._where = QB.WhereEqual(**key_values)
        return self

    @query_method
    def where_sql(self, query: str, *params: Any):
        self._body._where = QB.WhereSql(query, *params)
        return self

    @query_method
    def order_by(self, *columns_asc_desc: str):
        self._body._order_by = columns_asc_desc
        return self

    @query_method
    def limit(self, limit: Optional[int]):
        self._body._limit = limit
        return self

    @query_method
    def everywhere(self):
        self._body._where = QB.Everywhere()
        return self

    @query_method
    def and_where(self, **key_values):
        self._body._where = QB.WhereAnd(
            self._body._where,
            QB.WhereEqual(**key_values),
        )
        return self

    @query_method
    def and_where_sql(self, query: str, *params: Any):
        self._body._where = QB.WhereAnd(
            self._body._where,
            QB.WhereSql(query, *params),
        )
        return self

    # Select method and mutation methods

    @query_method
    def select(self, *columns: str):
        what = ', '.join(columns) or '*'
        params = []
        where = self._body._str(params)
        query = f'SELECT {what} FROM {self.name} {where}'
        return self.db._execute(query, params)

    @query_method
    def delete(self):
        QB.Where.assert_initialized(self._body._where)
        params = []
        where = self._body._str(params)
        query = f'DELETE FROM {self.name} {where}'
        return self.db._execute(query, params)

    @query_method
    def insert(self, **record: Data):
        #inst = 'INSERT OR IGNORE' if ignore else 'INSERT'
        where = self._body._str([]).strip()
        assert not where, f'Unexpected statements for INSERT: {where}'
        table = self.name
        keys, values = unzip(record)
        columns = ', '.join(keys)
        marks = ', '.join('?' for _ in keys)
        query = f'INSERT INTO {table} ({columns}) VALUES ({marks})'
        return self.db._execute(query, values)

    @query_method
    def insert_or_ignore(self, **record: Data):
        where = self._body._str([]).strip()
        assert not where, f'Unexpected statements for INSERT: {where}'
        table = self.name
        keys, values = unzip(record)
        columns = ', '.join(keys)
        marks = ', '.join('?' for _ in keys)
        query = f'INSERT OR IGNORE INTO {table} ({columns}) VALUES ({marks})'
        cursor = self.db._execute(query, values)
        return cursor.rowcount

    @query_method
    def update_or_ignore(self, **partial_record: Data):
        QB.Where.assert_initialized(self._body._where)
        keys, params = unzip(partial_record)
        what = ', '.join(f'{c} = ?' for c in keys)
        where = self._body._str(params)
        query = f'UPDATE {self.name} SET {what} {where}'
        cursor = self.db._execute(query, params)
        return cursor.rowcount

    @query_method
    def update(self, **partial_record: Data):
        if not self.update_or_ignore(**partial_record):
            assert isinstance(
                self._body._where, QB.WhereEqual
            ), '.where_sql(..).update(..) is unsupported. Use .where(..).update(..) instead'
            record = {
                **partial_record,
                **self._body._where.kwargs,
            }
            self._body._where = None
            self.insert(**record)
        return

    # high-level select methods

    @query_method
    def count(self):
        n = self.value('count(*)')
        return cast(int, n)

    # High-level methods with type argument

    @query_method
    def rows(self, *columns: str, type: Type = DataRow):
        rows = [*self.select(*columns)]
        return cast(List[type], rows)

    @query_method
    def dicts(self, *columns: str, type: Type = Record):
        cursor = self.select(*columns)
        names = [c for c, *_ in cursor.description]
        dicts = [dict(zip(names, row)) for row in cursor]
        return cast(List[type], dicts)

    @query_method
    def column(self, column: str, type: Type = Data):
        values = [first for first, *_ in self.rows(column)]
        return cast(List[type], values)

    @query_method
    def value(self, column: str, type: Type = Data):
        value = self.limit(1).column(column)[0]
        return cast(type, value)

    @query_method
    def dict(self, *columns: str, type: Type = Record):
        dict = self.limit(1).dicts(*columns)[0]
        return cast(type, dict)

    @query_method
    def get_value(self, column: str, type: Type = Data):
        col = self.limit(1).column(column, type=type)
        value = col[0] if col else None
        return cast(Optional[type], value)

    @query_method
    def get_dict(self, *columns: str, type: Type = Record):
        dicts = self.limit(1).dicts(*columns, type=type)
        record = dicts[0] if dicts else None
        return cast(Optional[type], record)

    @query_method
    def series(self, *columns: str, type: Type = Data):
        cursor = self.select(*columns)
        keys = [x[0] for x in cursor.description]
        out = {key: [] for key in keys}
        for row in cursor:
            for key, value in zip(keys, row):
                out[key].append(value)
        return cast(Dict[str, List[type]], out)

    # random selection methods

    @query_method
    def random_rows(self, n: int, *columns: str, type: Type = DataRow):
        rows, _ = self._select_random(n, *columns)
        return cast(List[type], rows)

    @query_method
    def random_dicts(self, n: int, *columns: str, type: Type = Record):
        rows, keys = self._select_random(n, *columns)
        dicts = [dict(zip(keys, row)) for row in rows]
        return cast(List[type], dicts)

    @query_method
    def random_values(self, n: int, column: str, type: Type = Data):
        rows = self.random_rows(n, column)
        values = [first for first, *_ in rows]
        return cast(List[type], values)

    @query_method
    def random_dict(self, *columns: str, type: Type = Record):
        dicts = self.random_dicts(1, *columns, type=type)
        return cast(type, dicts[0])

    @query_method
    def random_value(self, column: str, type: Type = Data):
        values = self.random_values(1, column, type=type)
        return cast(type, values[0])

    @query_method
    def _select_random(self, n: int, *columns: str):
        assert n > 0, 'Empty selection unsupported'
        N: int = self.count()
        assert N > 0, 'The table is empty'
        where = self._body._where
        column_names = []
        rows: List[List[Data]] = []
        while len(rows) < n:
            remaining = n - len(rows)
            # Filter many out randomly
            mod = 1 + N // (2 * remaining)
            print(mod)
            new_where = QB.WhereSql(f'random() % ? = 0', mod)
            if where is not None:
                new_where = QB.WhereAnd(where, new_where)
            self._body._order_by = ()
            self._body._where = new_where
            cursor = self.limit(remaining).select(*columns)
            column_names = [x[0] for x in cursor.description]
            rows.extend(cursor)
        shuffle(rows)
        return rows, column_names

    # high-level iter_select methods

    @query_method
    def iter_rows(self, *columns: str, type: Type = DataRow):
        total_approx = self.count()
        it = iter(self.select(*columns))
        it = cast(Iterator[type], it)
        return total_approx, it

    @query_method
    def iter_dicts(self, *columns: str, type: Type = Record):
        total_approx = self.count()
        cursor = self.select(*columns)
        names = [c for c, *_ in cursor.description]
        it = (dict(zip(names, row)) for row in cursor)
        it = cast(Iterator[type], it)
        return total_approx, it

    @query_method
    def iter_column(self, column: str, type: Type = Data):
        total_approx = self.count()
        it = iter(row[0] for row in self.select(column))
        it = cast(Iterator[type], it)
        return total_approx, it
