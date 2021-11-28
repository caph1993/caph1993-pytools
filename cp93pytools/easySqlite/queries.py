from __future__ import annotations
import abc
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union
if TYPE_CHECKING:
    from .table import SqliteTable, Record, Data

#Columns = Optional[Excluding[str, Sequence[str]]] # If Excluding existed
Columns = Optional[Union[List[str], Tuple[str, ...]]]
OrderBy = Optional[Union[List[str], Tuple[str, ...]]]
Params = List[Any]


class WhereClause(abc.ABC):

    @abc.abstractmethod
    def parse_into(self, params: Params) -> str:
        ...

    @abc.abstractmethod
    def keys(self) -> List[str]:
        ...

    def __or__(self, other: WhereClause):
        return WhereCompound(self, 'OR', other)

    def __and__(self, other: WhereClause):
        return WhereCompound(self, 'AND', other)

    def __str__(self):
        params = []
        where_str = self.parse_into(params)
        return f'Where query string:\n{where_str}\nwith parameters:\n{params}'


class Where(WhereClause):
    cmp_operators = ['=', '<>', '<', '>=', '>', '<=', 'LIKE']

    def __init__(self, key: str, cmp: str, value: Any):
        assert cmp in self.cmp_operators
        self.key = key
        self.cmp = cmp
        self.value = value

    def parse_into(self, params: Params):
        params.append(self.value)
        return f'{self.key} {self.cmp} ?'

    def keys(self):
        return [self.key]


class WhereCompound(WhereClause):
    operators = ['AND', 'OR']

    def __init__(self, first: WhereClause, op: str, second: WhereClause):
        assert op in self.operators
        self.first = first
        self.op = op
        self.second = second

    def parse_into(self, params: Params):
        first = self.first.parse_into(params)
        second = self.second.parse_into(params)
        return f'({first}) {self.op} ({second})'

    def keys(self):
        return [*self.first.keys(), *self.second.keys()]


class WhereEQ(WhereClause):
    '''
    Particular case of Where and WhereCompound:
        
        key1 = value1 AND key2 = value2 AND ...

    Implemented separately for speed because it is very common 
    '''

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def parse_into(self, params: Params):
        keys, values = zip(*self.kwargs.items())
        params.extend(values)
        return ' AND '.join(f'{k} = ?' for k in keys)

    def keys(self):
        return [*self.kwargs.keys()]


class QueryPart(abc.ABC):

    @abc.abstractmethod
    def parse_into(self, params: Params) -> str:
        ...

    @abc.abstractmethod
    def keys(self) -> List[str]:
        ...

    def strict_check(self, table: SqliteTable, query_str: str):
        found = set(self.keys())
        expected = set(table.columns())
        diff = found.difference(expected)
        assert not diff, (f'Unknown columns for table {table.table_name}:\n'
                          f'{diff} not in {expected}\n'
                          f'Unsafe query (details above):\n{query_str}')
        return


class QueryBody(QueryPart):

    def __init__(self, complex_where: WhereClause = None,
                 order_by: OrderBy = None, limit: int = None, **where):
        if complex_where is None:
            _where = WhereEQ(**where) if where else None
        else:
            assert not where, ('Use one of (..., complex_where=...) or'
                               ' (..., **where), but not both')
            _where = complex_where
        self.order_by = order_by
        self.limit = limit
        self.where = _where

    def parse_into(self, params: Params):
        body = []
        if self.where is not None:
            where_str = self.where.parse_into(params)
            body.append(f'WHERE {where_str}')
        if self.order_by is not None:
            by = ', '.join(self.order_by)
            body.append(f'ORDER BY {by}')
        if self.limit is not None:
            body.append('LIMIT ?')
            params.append(int(self.limit))
        return ' '.join(body)

    def keys(self):
        keys = self.where.keys() if self.where else []
        if self.order_by is not None:
            for by in self.order_by:
                col, *s = by.split(maxsplit=1)
                keys.append(col)
                asc_desc = s[0].lower().strip()
                assert asc_desc in ('', 'asc', 'desc', 'ascending',
                                    'descending'), asc_desc
        return keys


class QueryHead(QueryPart):

    def keys(self):
        return []


class QueryHeadSelect(QueryHead):

    def __init__(self, columns: Columns, table: SqliteTable):
        self.table = table
        self.columns = columns

    def parse_into(self, params: Params):
        what = '*' if not self.columns else ', '.join(self.columns)
        return f'SELECT {what} FROM {self.table.table_name}'


class QueryHeadDelete(QueryHead):

    def __init__(self, table: SqliteTable):
        self.table = table

    def parse_into(self, params: Params):
        return f'DELETE FROM {self.table.table_name}'


class QueryHeadInsert(QueryHead):

    def __init__(self, record: Record, table: SqliteTable, ignore=False):
        self.table = table
        self.record = record
        self.inst = 'INSERT OR IGNORE' if ignore else 'INSERT'

    def parse_into(self, params: Params):
        table = self.table.table_name
        keys, values = zip(*self.record.items())
        columns = ', '.join(keys)
        marks = ', '.join('?' for _ in keys)
        params.extend(values)
        return f'{self.inst} INTO {table} ({columns}) VALUES ({marks})'

    def keys(self):
        return [*self.record.keys()]


class QueryHeadUpdate(QueryHead):

    def __init__(self, record: Record, table: SqliteTable):
        self.table = table
        self.record = record

    def parse_into(self, params: Params):
        table = self.table.table_name
        keys, values = zip(*self.record.items())
        what = ', '.join(f'{c} = ?' for c in keys)
        params.extend(values)
        return f'UPDATE {table} SET {what}'

    def keys(self):
        return [*self.record.keys()]
