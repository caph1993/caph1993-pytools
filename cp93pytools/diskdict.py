from __future__ import annotations
from collections import deque, Counter, OrderedDict
import json
from json import encoder
import sqlite3
from types import FunctionType
from typing import Any, Callable, Dict, Generic, List, Mapping, Optional, Sequence, Tuple, Type, TypeVar, Union

DictEncoder = Tuple[Type, Callable[[Any], Dict]]
ListEncoder = Tuple[Type, Callable[[Any], List]]

JSONLike = Union[str, int, float, bool, None,
                 object]  # (recursive type hotfix, May 2021)


class CustomJSON:

    default_list_encoders: List[ListEncoder] = [
        (tuple, list),
        (deque, list),
        (set, list),
        (frozenset, list),
    ]
    default_dict_encoders: List[DictEncoder] = [
        (Counter, dict),
        (OrderedDict, dict),
    ]

    json_types: Sequence[Type] = [dict, list, int, str, float, bool, type(None)]

    def __init__(self, list_encoders: List[ListEncoder] = None,
                 dict_encoders: List[DictEncoder] = None):
        'encoders is a dict [class]->converter, where class has a __name__ and'
        'converter converts class into a list or a dict'
        self.list_encoders = dict(
            [*self.default_list_encoders, *(list_encoders or [])])
        self.dict_encoders = dict(
            [*self.default_dict_encoders, *(dict_encoders or [])])

    def stringify(self, obj: object):
        return self._stringify(obj)[1]

    def _stringify(self, obj: object):
        pre_dumped = self.pre_dump(obj)
        return pre_dumped, json.dumps(obj)

    def parse(self, text: str):
        return self.post_load(json.loads(text))

    def save(self, fname: str, obj: object):
        with open(fname, 'w') as f:
            json.dump(self.pre_dump(obj), f)

    def load(self, fname: str):
        with open(fname, 'r') as f:
            obj: JSONLike = json.load(f)
        return self.post_load(obj)

    def pre_dump(self, obj: object) -> JSONLike:
        'convert obj into a JSON serializable object recursively'
        out = self._prefix_pre_dump(obj)
        if isinstance(out, dict):
            out = {k: self.pre_dump(v) for k, v in out.items()}
        elif isinstance(out, list):
            out = [self.pre_dump(v) for v in out]
        return out

    def _prefix_pre_dump(self, obj: object):
        'convert obj to a JSON serializable only on the first depth level'
        'add prefixes for storing decoding info'
        if isinstance(obj, dict):
            return {(f'**{k}' if k.startswith('*') else k): v
                    for k, v in obj.items()}
        for cls, to_js in self.list_encoders.items():
            if isinstance(obj, cls):
                return {'*': cls.__name__, '**': to_js(obj)}
        for cls, to_js in self.dict_encoders.items():
            if isinstance(obj, cls):
                return {'*': cls.__name__, **self._prefix_pre_dump(to_js(obj))}
        if any(isinstance(obj, cls) for cls in self.__class__.json_types):
            return obj
        raise Exception(f'Unknown class {type(obj)} of object:\n{obj}')

    def post_load(self, loaded: JSONLike) -> object:
        'convert loaded JSONLike into decoded classes recursively'
        out: object = loaded
        if isinstance(out, list):
            out = [self.post_load(v) for v in out]
        elif isinstance(out, dict):
            out = {k: self.post_load(v) for k, v in out.items()}
            out = self._prefix_post_load(out)
        return out

    def _prefix_post_load(self, loaded: dict[str, JSONLike]):
        out: object = loaded
        if '*' in out:
            clsname = out.pop('*')
            cls = self.decoders[clsname]
            out = cls(out.pop('**'))
        # Undo dumped ficticious prefixes
        if isinstance(out, dict):
            out = {
                (k[2:] if k.startswith('**') else k): v for k, v in out.items()
            }
        return out

    @property
    def decoders(self):
        decoders = {
            **{cls.__name__: cls for cls in self.list_encoders},
            **{cls.__name__: cls for cls in self.dict_encoders}
        }
        return decoders


class DiskDict:
    '''
    Holds a dictionary in disk (sqlite3) using a CustomJSON class for conversion
      Keys must be text.
      Values must support serialization with JSON.parse
    
    If values are dictionaries, some queries on their keys are supported.
    
    #ToDo: Strings are forcibly unidecoded and lowercased to facilitate indexing
    '''

    def __init__(self, file=':memory:', JSON=None, indices=None):
        self.connection = sqlite3.connect(file)

        self.connection.execute(f'''
      CREATE TABLE IF NOT EXISTS objects(
        key TEXT NOT NULL PRIMARY KEY,
        obj TEXT NOT NULL)''')
        self.connection.execute('''
      CREATE TABLE IF NOT EXISTS indexed(
        key TEXT NOT NULL)''')
        self.JSON = JSON or CustomJSON()
        self.add_indices(indices or [])

    def _execommit(self, *query):
        try:
            self.connection.execute(*query)
        except Exception as e:
            raise Exception(*query) from e
        self.connection.commit()

    def _iterrows(self, *query):
        yield from self.connection.execute(*query)

    def _itercol(self, *query):
        it = (t for t, *_ in self._iterrows(*query))
        yield from it

    def __iter__(self):
        q = (f'SELECT key FROM objects',)
        yield from self._itercol(*q)

    def __contains__(self, key):
        q = (f'SELECT key FROM objects WHERE key=?', (key,))
        yield any(k == key for k in self._itercol(*q))

    def __getitem__(self, key):
        q = (f'SELECT obj FROM objects WHERE key=?', (key,))
        found = list(map(self.JSON.parse, self._itercol(*q)))
        if not found:
            raise KeyError(key)
        return found.pop()

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def items(self):
        q = (f'SELECT key, obj FROM objects',)
        for key, obj in self.connection.execute(*q):
            yield key, self.JSON.parse(obj)

    def values(self):
        q = (f'SELECT obj FROM objects',)
        yield from map(self.JSON.parse, self._itercol(*q))

    def __setitem__(self, key, obj):
        pre_dumpd, value = self.JSON._stringify(obj)
        if key in self:
            self._del_indexed(key)
        self._insert_indexed(((key, pre_dumpd),))
        self._execommit(f'REPLACE INTO objects VALUES (?,?)', (key, value))

    @property
    def indexed(self):
        value = self.__dict__.get('__indexed')
        if value is None:
            value = self._table_columns('indexed')[1:]
            self.__dict__['__indexed'] = value
        return value

    def _insert_indexed(self, items, table='indexed'):
        if table == 'indexed':
            indexed = self.indexed
        else:
            indexed = self._table_columns(table)[1:]
        qmark = ','.join('?' for _ in range(len(indexed) + 1))
        query = f'INSERT INTO {table} VALUES ({qmark})'
        for key, obj in items:
            if hasattr(obj, 'get'):
                values = (obj.get(key) for key in indexed)
                self._execommit(query, (key, *values))

    def Keys(self):
        return list(self)

    def Values(self):
        return list(self.values())

    def Items(self):
        return list(self.items())

    def Dict(self):
        return dict(self.items())

    def indexed_items(self):
        yield from self.connection.execute(f'SELECT * FROM indexed')

    def where_query(self, params, limit: Optional[int]):
        'Usage: see self.where'
        indexed = self.indexed
        values = []

        def parse(column, eq, value):
            nonlocal values, indexed
            if eq.lower() in ('and', 'or'):
                return f'({parse(*column)} {eq} {parse(*value)})'
            assert eq in ('==', '!=', '<', '<=', '>',
                          '>='), f'Invalid operator: {eq}'
            assert column in indexed, f'Can not run query on non-indexed column "{column}"'
            if value is None:
                assert eq in ('==', '!='), f'Invalid operator with NULL: {eq}'
                if eq == '==':
                    return f'({column} IS NULL)'
                return f'({column} IS NOT NULL)'
            if eq == '!=':
                eq = '<>'
            elif eq == '==':
                eq = '='
            values.append(value)
            return f'({column} {eq} ?)'

        qlimit = '' if limit is None else f'LIMIT {limit}'
        return (f'SELECT key FROM indexed WHERE {parse(*params)} {qlimit}',
                values)

    def where(self, params, limit=None):
        '''
    Usage:
      where((column, '<', value), limit=10)
      where(((('n', '==', 3), 'and', ('k', '>=', 4)), 'or' ('name', '!=', 'carlos')))
    '''
        q = self.where_query(params, limit=limit)
        yield from (self[key] for key in self._itercol(*q))

    def __delitem__(self, key):
        self._execommit(f'DELETE FROM objects WHERE key=?', (key,))
        self._del_indexed(key)

    def _del_indexed(self, key):
        self._execommit(f'DELETE FROM indexed WHERE key=?', (key,))

    def del_index(self, column):
        assert column != 'key'
        self._execommit(
            f'CREATE TABLE tmp_indexed AS SELECT * FROM indexed WHERE 1=0')
        self._execommit(f'ALTER TABLE tmp_indexed DROP COLUMN {column}')
        self._insert_indexed(self.items(), table='tmp_indexed')
        self._execommit(f'ALTER TABLE indexed RENAME TO tmp__indexed')
        self._execommit(f'ALTER TABLE tmp_indexed RENAME TO indexed')
        self._execommit(f'DROP TABLE IF EXISTS tmp__indexed')

    def _table_columns(self, table):
        q = (f'SELECT name FROM PRAGMA_TABLE_INFO(?)', (table,))
        return list(self._itercol(*q))

    def __len__(self):
        return next(self._itercol(f'SELECT COUNT(key) FROM objects'))

    def add_indices(self, indices):
        for column, sql_type in indices:
            self.add_index(column, sql_type)

    def add_index(self, column, sql_type):
        if column not in self.indexed:
            self._add_index(column, sql_type)

    def _add_index(self, column, sql_type):
        self._execommit(f'DROP TABLE IF EXISTS tmp_indexed')
        self._execommit(
            f'CREATE TABLE tmp_indexed AS SELECT * FROM indexed WHERE 1=0')
        self._execommit(
            f'ALTER TABLE tmp_indexed ADD COLUMN {column} {sql_type}')
        self._insert_indexed(self.items(), table='tmp_indexed')
        self._execommit(f'ALTER TABLE indexed RENAME TO tmp__indexed')
        self._execommit(f'ALTER TABLE tmp_indexed RENAME TO indexed')
        self._execommit(f'DROP TABLE IF EXISTS tmp__indexed')
        self.__dict__.pop('__indexed', None)
