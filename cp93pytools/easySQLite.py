from __future__ import annotations
from collections import deque, Counter, OrderedDict
from contextlib import contextmanager
import json, time, random, logging
from sqlite3.dbapi2 import ProgrammingError
from json import encoder
import sqlite3
from types import FunctionType
from typing import Any, Callable, Dict, Generic, Iterable, List, Literal, Mapping, Optional, Tuple, Type, TypeVar, Union


def custom_repr(self, *keys):
    name = self.__class__.__name__
    comma_kwargs = ', '.join(f'{k}={repr(getattr(self, k))}' for k in keys)
    return f'{name}({comma_kwargs})'


#Params = Excluding[str, Sequence[Any]] # If Excluding existed
#Columns = Excluding[str, Sequence[str]] # If Excluding existed
Params = Union[List[Any], Tuple[Any, ...]]
Columns = Union[List[str], Tuple[str, ...]]


class SQLiteDB:
    '''
    '''

    def __repr__(self):
        return custom_repr(self, 'file')

    def __init__(self, file=':memory:'):
        self.file = file

    def new_connection(self):
        return sqlite3.connect(self.file, check_same_thread=False)

    def _execute(self, query: str, params: Params = None) -> sqlite3.Cursor:
        assert not isinstance(params, str), f'Did you mean params=[{params}]?'
        try:
            with self.new_connection() as con:
                return con.execute(query, params or [])
        except sqlite3.Error as e:
            e.args = (*e.args, query, params)
            raise e

    def execute(self, query: str, params: Params = None) -> List[Any]:
        return [*self._execute(query, params or [])]

    def execute_column(self, query: str, params: Params = None):
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

    _query_index_names = """
        SELECT name FROM sqlite_master 
        WHERE type = 'index' 
        ORDER BY 1;
    """

    def index_names(self):
        return self.execute_column(self._query_index_names)

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

    def get_key_value_table(self, table_name: str):
        return self.get_table(table_name).as_key_value()

    def table_columns(self, table_name: str):
        return self.get_table(table_name).columns()

    def table_count(self, table_name: str):
        return len(self.get_table(table_name))


class SQLiteTable:

    def __init__(self, file: str, table_name: str):
        self.file = file
        self.table_name = table_name
        self.db = SQLiteDB(self.file)

    def __repr__(self):
        return custom_repr(self, 'file', 'table_name')

    _query_columns = """
    SELECT name FROM PRAGMA_TABLE_INFO(?)
    """

    def columns(self):
        return self.db.execute_column(self._query_columns, [self.table_name])

    def __len__(self) -> int:
        query = f'SELECT COUNT(*) FROM {self.table_name}'
        return self.db.execute(query)[0][0]

    def insert_row(self, **kwargs):
        assert kwargs, 'Nothing to set'
        table = self.table_name
        columns = ', '.join(kwargs.keys())
        marks = ', '.join('?' for _ in kwargs)
        query = f'INSERT INTO {table} ({columns}) VALUES ({marks})'
        params = [*kwargs.values()]
        return self.db._execute(query, params)

    def _make_query(self, columns: Columns = None, where: str = None):
        table = self.table_name
        what = self._make_columns(columns)
        query = f'SELECT {what} FROM {table}'
        if where is not None:
            query = f'{query} WHERE {where}'
        return query

    def _make_columns(self, columns: Columns = None):
        if columns is None:
            comma_columns = '*'
        else:
            # Security check:
            assert set(columns) <= set(self.columns())
            comma_columns = ','.join(columns)
        return comma_columns

    def rows(self, columns: Columns = None, where: str = None,
             params: Params = None):
        query = self._make_query(columns, where)
        return self.db.execute(query, params)

    def _to_dict_map(self, columns: Columns = None):
        columns = self.columns() if not columns else columns
        to_dict = lambda row: dict(zip(columns, row))
        return to_dict

    def dicts(self, columns: Columns = None, where: str = None,
              params: Params = None):
        rows = self.rows(columns, where, params)
        to_dict = self._to_dict_map(columns)
        return [to_dict(row) for row in rows]

    def column(self, field: str = None, where: str = None,
               params: Params = None):
        columns = None if field is None else [field]
        return [r[0] for r in self.rows(columns, where, params)]

    def unique_dict(self, columns: Columns = None, where: str = None,
                    params: Params = None):
        dicts = self.dicts(columns, where, params)
        n = len(dicts)
        assert n <= 1, f'Multiple ({n}) results, e.g.: {dicts[:2]}'
        return dicts[0] if dicts else None

    def get_first_dict(self, columns: Columns = None):
        return self.unique_dict(columns, '1=1 LIMIT 1', None)

    def indexed_by(self, index_columns: List[str]):
        return IndexedSQLiteTable(
            self.file,
            self.table_name,
            index_columns,
        )

    def as_key_value(self):
        return KeyValueSQLiteTable(self.file, self.table_name)


class IndexedSQLiteTable(SQLiteTable):

    _repr_keys = ['file', 'table_name', 'index_columns']

    def __init__(self, file: str, table_name: str, index_columns: List[str]):
        super().__init__(file, table_name)
        self.index_columns = index_columns

    def __repr__(self):
        return custom_repr(self, 'file', 'table_name', 'index_columns')

    def _where(self):
        columns = self.index_columns
        return ' AND '.join(f'{c}=?' for c in columns)

    def get_row(self, *idx: Any, columns: Columns = None):
        assert idx, 'Nowhere to get'
        where = self._where()
        rows = self.rows(columns, where, idx)
        return rows[0] if rows else None

    def get_dict(self, *idx: Any, columns: Columns = None):
        assert idx, 'Nowhere to get'
        where = self._where()
        dicts = self.dicts(columns, where, idx)
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
        if not self.update_row(*idx, **kwargs):
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


class KeyValueSQLiteTable(SQLiteTable):

    def __init__(self, file: str, table_name: str):
        super().__init__(file, table_name)
        self.db.execute(f'''
        CREATE TABLE IF NOT EXISTS {self.table_name}(
            key text NOT NULL PRIMARY KEY,
            value text,
            lock_token double NOT NULL,
            locked_until double NOT NULL
        )
        ''')
        the_columns = {'key', 'value', 'lock_token', 'locked_until'}
        assert set(self.columns()) == the_columns, self.columns()
        return

    @contextmanager
    def exclusive_access(self, *keys: str, delta=0.02, max_duration=0.5):
        assert keys, 'You must specify keys to be locked explicitely'
        token = 1 + random.random()
        for key in keys:
            self._lock(key, token, delta, max_duration)
        try:
            yield
        finally:
            for key in keys:
                self._unlock(key, token, max_duration)
        return

    def _current_lock(self, key: str):
        lock_keys = ['lock_token', 'locked_until']
        return super().unique_dict(lock_keys, 'key=?', [key])

    def _lock(self, key: str, token: float, delta=0.02, max_duration=1.5):
        while True:
            d = self._current_lock(key)
            if (not d or d['lock_token'] == 0 or
                    time.time() > d['locked_until']):
                # Request access, race until next loop
                super().indexed_by(['key']).set_row(
                    key,
                    lock_token=token,
                    locked_until=time.time() + max_duration,
                )
            elif d['lock_token'] == token:
                break  # Access gained
            time.sleep(delta)
        return

    def _unlock(self, key: str, token: float, max_duration: float):
        d = self._current_lock(key)
        if not d:
            logging.warning(
                f'Key {repr(key)} was deleted by another thread or process during exclusive access'
            )
            return
        remaining = d['locked_until'] - time.time()
        if remaining < 0:
            ms = round(-remaining * 1000)
            logging.warning(
                f'Locked {repr(key)} during {ms}ms more than max_duration={max_duration}s'
            )
        if d['lock_token'] == token:
            super().indexed_by(['key']).set_row(key, lock_token=0)
        return

    def __getitem__(self, key: str):
        d = super().unique_dict(['value'], 'key=?', [key])
        if not d:
            raise KeyError(key)
        return json.loads(d['value'] or 'null')

    def __setitem__(self, key: str, value: Any):
        super().indexed_by(['key']).set_row(key, value=json.dumps(value))
        return

    def values(self):
        return [json.loads(s or 'null') for s in super().column('value')]

    def keys(self) -> List[str]:
        return [k for k in super().column('key')]

    def items(self) -> List[Tuple[str, Any]]:
        items = super().rows(['key', 'value'])
        return [(k, json.loads(v or 'null')) for k, v in items]

    def get(self, key: str, default=None):
        try:
            return self[key]
        except KeyError:
            return default


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
    table = db.get_table('test1').as_key_value()
    with table.exclusive_access('last_time', 'last_progress'):
        print('I HAVE ACCESS!')