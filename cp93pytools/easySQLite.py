from __future__ import annotations
from collections import deque, Counter, OrderedDict
import json
from json import encoder
import sqlite3
from types import FunctionType
from typing import Any, Callable, Dict, Generic, Iterable, List, Literal, Mapping, Optional, Sequence, Tuple, Type, TypeVar, Union


def custom_repr(self, *keys):
    name = self.__class__.__name__
    comma_kwargs = ', '.join(f'{k}={repr(getattr(self, k))}' for k in keys)
    return f'{name}({comma_kwargs})'


class SQLiteDB:
    '''
    '''

    def __repr__(self):
        return custom_repr(self, 'file')

    def __init__(self, file=':memory:'):
        self.file = file

    def new_connection(self):
        return sqlite3.connect(
            self.file,
            check_same_thread=False,
        )

    def _execute(
        self,
        query: str,
        params: Iterable[Any] = None,
    ) -> sqlite3.Cursor:
        try:
            with self.new_connection() as con:
                return con.execute(query, params or [])
        except sqlite3.OperationalError as e:
            e.args = (*e.args, query, str(params))
            raise e

    def execute(
        self,
        query: str,
        params: Iterable[Any] = None,
    ) -> List[Any]:
        return [*self._execute(query, params or [])]

    def execute_column(
        self,
        query: str,
        params: Iterable[Any] = None,
    ):
        rows = self.execute(query, params)
        return [first for first, *_ in rows]

    _query_table_names = """
    SELECT name FROM sqlite_master 
    WHERE type = 'table' 
    AND name NOT LIKE 'sqlite_%'
    ORDER BY 1;
    """

    def table_names(self):
        return self.execute_column(self._query_table_names)

    _query_table_columns = """
    SELECT name FROM PRAGMA_TABLE_INFO(?)
    """

    def table_columns(self, table_name: str):
        return self.execute_column(
            self._query_table_columns,
            [table_name],
        )

    def tables(self):
        names = self.table_names()
        return {t: self.get_table(t) for t in names}

    def get_table(self, table_name: str):
        return SQLiteTable(self.file, table_name)

    def get_indexed_table(
        self,
        table_name: str,
        index_columns: List[str],
    ):
        table = self.get_table(table_name)
        return table.indexed_by(index_columns)

    _query_index_names = """
        SELECT name FROM sqlite_master 
        WHERE type = 'index' 
        ORDER BY 1;
    """

    def index_names(self):
        return self.execute_column(self._query_index_names)

    def table_iter(self, table_name: str):
        with self.new_connection() as con:
            return con.execute("SELECT * FROM ?", [table_name])

    def table_count(self, table_name: str):
        query = f'SELECT COUNT(*) FROM {table_name}'
        return self.execute(query)[0][0]

    def table_all_rows(self, table_name: str):
        return [*self.table_iter(table_name)]


class SQLiteTable:

    def __init__(self, file: str, table_name: str):
        self.file = file
        self.table_name = table_name
        self.db = SQLiteDB(self.file)

    def __repr__(self):
        return custom_repr(self, 'file', 'table_name')

    def columns(self):
        return self.db.table_columns(self.table_name)

    def __iter__(self):
        return self.db.table_iter(self.table_name)

    def all_rows(self):
        return self.db.table_all_rows(self.table_name)

    def indexed_by(self, index_columns: List[str]):
        return IndexedSQLiteTable(
            self.file,
            self.table_name,
            index_columns,
        )

    def __len__(self) -> int:
        return self.db.table_count(self.table_name)

    def insert_row(self, **kwargs):
        assert kwargs, 'Nothing to set'
        table = self.table_name
        fields = ', '.join(kwargs.keys())
        marks = ', '.join('?' for _ in kwargs)
        query = f'INSERT INTO {table} ({fields}) VALUES ({marks})'
        params = [*kwargs.values()]
        return self.db._execute(query, params)

    def _to_dict_map(self, fields: Sequence[str] = None):
        fields = self.columns() if not fields else fields
        f = lambda row: dict(zip(fields, row))
        return f

    def _fields(self, fields: Sequence[str] = None):
        if fields is None:
            comma_fields = '*'
        else:
            # Security check:
            assert set(fields) <= set(self.columns())
            comma_fields = ','.join(fields)
        return comma_fields

    def get_rows_where(self, where: str, args: Iterable[Any] = None,
                       fields: Sequence[str] = None):
        table = self.table_name
        what = self._fields(fields)
        query = f'SELECT {what} FROM {table} WHERE {where}'
        return self.db.execute(query, args)

    def get_dicts_where(self, where: str, args: Iterable[Any] = None,
                        fields: Sequence[str] = None):
        rows = self.get_rows_where(where, args, fields)
        to_dict = self._to_dict_map(fields)
        return [to_dict(row) for row in rows]

    def get_unique_dict_where(self, where: str, args: Iterable[Any] = None,
                              fields: Sequence[str] = None):
        dicts = self.get_dicts_where(where, args, fields)
        n = len(dicts)
        assert n <= 1, f'Multiple ({n}) results, e.g.: {dicts[:2]}'
        return dicts[0] if dicts else None

    def get_first_dict(self, fields: Sequence[str] = None):
        return self.get_unique_dict_where('1=1 LIMIT 1', None, fields)


class IndexedSQLiteTable(SQLiteTable):

    _repr_keys = ['file', 'table_name', 'index_columns']

    def __init__(
        self,
        file: str,
        table_name: str,
        index_columns: List[str],
    ):
        self.file = file
        self.table_name = table_name
        self.index_columns = index_columns
        self.db = SQLiteDB(self.file)

    def __repr__(self):
        return custom_repr(self, 'file', 'table_name', 'index_columns')

    def _where(self):
        columns = self.index_columns
        return ' AND '.join(f'{c}=?' for c in columns)

    def get_row(self, *idx: Any, fields: Sequence[str] = None):
        assert idx, 'Nowhere to get'
        where = self._where()
        rows = self.get_rows_where(where, idx, fields)
        return rows[0] if rows else None

    def get_dict(self, *idx: Any, fields: Sequence[str] = None):
        assert idx, 'Nowhere to get'
        where = self._where()
        dicts = self.get_dicts_where(where, idx, fields)
        return dicts[0] if dicts else None

    def update_row(self, *idx: Any, **kwargs):
        assert idx, 'Nowhere to set'
        assert kwargs, 'Nothing to set'
        table = self.table_name
        what = ', '.join(f'{c}=?' for c in kwargs.keys())
        where = self._where()
        query = f'UPDATE {table} SET {what} WHERE {where}'
        params = [*kwargs.values(), *idx]
        cur = self.db._execute(query, params)
        did_update = (cur.rowcount > 0)
        return did_update

    def set_row(self, *idx: Any, **kwargs):
        assert idx, 'Nowhere to set'
        for c, v in zip(self.index_columns, idx):
            if c in kwargs and kwargs[c] != v:
                msg = (f'Inconsistent idx and kwargs at column ({c}):'
                       f' ({v}) vs ({kwargs[c]})')
                raise Exception(msg)
            kwargs[c] = v
        if not self.update_row(idx, **kwargs):
            self.insert_row(**kwargs)
        return

    def del_row(self, *idx: Any):
        assert idx, 'Nowhere to del'
        table = self.table_name
        where = self._where()
        query = f'DELETE FROM {table} WHERE {where}'
        cur = self.db._execute(query, idx)
        did_del = cur.rowcount
        return did_del


def test():
    db = SQLiteDB('.test.db')
    db.execute(f'''
    CREATE TABLE IF NOT EXISTS objects(
        key TEXT NOT NULL PRIMARY KEY,
        obj TEXT NOT NULL
    )''')
    db.execute('''
    CREATE TABLE IF NOT EXISTS indexed(
        key TEXT NOT NULL
    )''')
    #print(db.tables())
    #print(db.index_names())
    #print(db.execute('SELECT * FROM sqlite_master'))
    ob = db.get_indexed_table('objects', ['key'])
    print(ob)
    print(len(ob))
    ob.set_row('key1', obj='VALUE1')
    print(ob.get_row('key1'))
    print(len(ob))