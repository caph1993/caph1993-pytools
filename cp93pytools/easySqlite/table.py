from __future__ import annotations
import abc
from os import times
from typing import TYPE_CHECKING, Any, Dict, List, cast
from .database import SqliteDB, FilePath, custom_repr, Data
from .queries import (
    Columns,
    QueryBody,
    QueryHead,
    QueryHeadSelect,
    QueryHeadDelete,
    QueryHeadInsert,
    QueryHeadUpdate,
)
from .table_signatures_ import table_signatures as T
# from ..methodtools import cached_property
Record = Dict[str, Data]


class SqliteTable(SqliteDB):
    '''
    Sqlite table object.

    count(**kw) -> int
    columns() -> List[str]

    dicts(columns, **kw)      -> List[Record] : (Record=Dict[str, Data])
    column(column, **kw)      -> List[Data]
    series(columns, **kw)     -> Dict[str, List[Data]]
    rows(columns, **kw)       -> List[Tuple[Data]]
    
    dict(columns, **kw)       -> first Record (or Exception)
    get_dict(columns, **kw)   -> first Record | None

    value(column, **kw)       -> first value (or Exception)
    get_value(column, **kw)   -> first value | None
    '''

    def __init__(self, file: FilePath, table_name: str, strict: bool = False):
        self.file = file
        self.table_name = table_name
        self.db = SqliteDB(self.file)
        self.strict = strict

    def __repr__(self):
        return custom_repr(self, 'file', 'table_name')

    def __len__(self):
        return self.count()

    # Main high-level mutation methods

    def insert(self, partial_record: Record):
        body = QueryBody()
        head = QueryHeadInsert(partial_record, self)
        return self._run_query(head, body)

    def insert_or_ignore(self, partial_record: Record):
        body = QueryBody()
        head = QueryHeadInsert(partial_record, self, ignore=True)
        cursor = self._run_query(head, body)
        return cursor.rowcount

    @T.delete
    def delete(self, **kw):
        assert kw, 'Nowhere to del'
        body = QueryBody(**kw)
        head = QueryHeadDelete(self)
        cur = self._run_query(head, body)
        return cur.rowcount

    @T.update
    def update(self, partial_record: Record, **kw):
        if self.update_or_ignore(partial_record, **kw) == 0:
            self.insert(partial_record)
        return

    @T.update_or_ignore
    def update_or_ignore(self, partial_record: Record, **kw):
        body = QueryBody(**kw)
        head = QueryHeadUpdate(partial_record, self)
        cursor = self._run_query(head, body)
        return cursor.rowcount

    # Main high-level select methods

    def columns(self) -> List[str]:
        query_str = 'SELECT name FROM PRAGMA_TABLE_INFO(?)'
        return self.db.execute_column(query_str, [self.table_name])

    @T.dicts
    def dicts(self, *columns: str, **kw):
        body = QueryBody(**kw)
        return self._select_dicts(columns, body)

    @T.column
    def column(self, column: str, **kw):
        body = QueryBody(**kw)
        return self._select_column(column, body)

    @T.series
    def series(self, *columns: str, **kw):
        body = QueryBody(**kw)
        return self._select_series(columns, body)

    @T.rows
    def rows(self, *columns: str, **kw):
        body = QueryBody(**kw)
        return self._select_rows(columns, body)

    @T.dict
    def dict(self, *columns: str, **kw):
        return self.dicts(*columns, **kw)[0]

    @T.get_dict
    def get_dict(self, *columns: str, **kw):
        dicts = self.dicts(*columns, **kw)
        return dicts[0] if dicts else None

    @T.value
    def value(self, column: str, **kw):
        kw['limit'] = 1
        return self.column(column, **kw)[0]

    @T.get_value
    def get_value(self, column: str, **kw):
        kw['limit'] = 1
        values = self.column(column, **kw)
        return values[0] if values else None

    @T.count
    def count(self, **kw):
        return int(self.value('count(*)'))

    # Low-level select methods

    def _run_query(self, head: QueryHead, body: QueryBody):
        params: List[Any] = []
        head_str = head.parse_into(params)
        body_str = body.parse_into(params)
        query_str = f'{head_str} {body_str}'
        if self.strict:
            head.strict_check(self, query_str)
            body.strict_check(self, query_str)
        return self.db._execute(query_str, params)

    def _select_rows(self, columns: Columns, body: QueryBody):
        head = QueryHeadSelect(columns, self)
        return [*self._run_query(head, body)]

    def _select_dicts(self, columns: Columns, body: QueryBody):
        rows = self._select_rows(columns, body)
        to_dict = self._to_dict_map(columns)
        return [to_dict(row) for row in rows]

    def _to_dict_map(self, columns: Columns):
        columns = columns or self.columns()
        to_dict = lambda row: dict(zip(columns, row))
        return to_dict

    def _select_column(self, column: str, body: QueryBody):
        rows = self._select_rows([column], body)
        return [first for first, *_ in rows]

    def _select_series(self, columns: Columns, body: QueryBody):
        keys = self.columns() if columns is None else columns
        out = {key: [] for key in keys}
        for row in self._select_rows(columns, body):
            for key, value in zip(keys, row):
                out[key].append(value)
        return out
