 
from collections import deque, Counter,OrderedDict
import json
import sqlite3


class CustomJSON:
    
    default_encoders = (
        (tuple, list),
        (deque, list),
        (set, list),
        (frozenset, list),
        (Counter, dict),
        (OrderedDict, dict),
    )
    
    def __init__(self, encoders=None, defaults=True):
        'encoders is a dict [class]->converter, where class has a __name__ and'
        'converter converts class into a list or a dict'
        if defaults:
            defaults = dict(self.__class__.default_encoders)
        else:
            defaults = {}
        self.encoders = {**defaults, **(encoders or {})}
    
    def stringify(self, obj):
        return json.dumps(self.pre_encode(obj))
    
    def _stringify(self, obj):
        pre_encoded = self.pre_encode(obj)
        return pre_encoded, json.dumps(obj)
    
    def parse(self, text):
        return self.post_decode(json.loads(text))
    
    def save(self, fname, obj):
        with open(fname, 'w') as f:
            json.dump(f, self.pre_encode(obj))
    
    def load(self, fname):
        with open(fname, 'r') as f:
            obj = json.load(f)
        return self.post_decode(obj)
    
    def pre_encode(self, obj):
        'convert obj into a JSON serializable object recursively'
        out = self._pre_encode(obj)
        if isinstance(out, dict):
            out = {k:self.pre_encode(v) for k,v in out.items()}
        elif isinstance(out, list):
            out = [self.pre_encode(v) for v in out]
        return out

    def _pre_encode(self, obj):
        'converts obj to a JSON serializable only on the first depth level'
        if isinstance(obj, dict):
            return {(f'**{k}' if k.startswith('*') else k):v for k,v in obj.items()}
        for cls, to_js in self.encoders.items():
            if isinstance(obj, cls):
                out = to_js(obj)
                if isinstance(out, dict):
                    out = {'*':cls.__name__, **self._pre_encode(out)}
                else:
                    out = {'*':cls.__name__, '**': out}
                return out
        if any(isinstance(obj, cls) for cls in (dict, list, int, str, float, bool)) or obj is None:
            return obj
        raise Exception(f'Unknown class {type(obj)} of object:\n{obj}')
    
    def post_decode(self, obj):
        decoders = {cls.__name__:cls for cls in self.encoders}
        
        def post_decode(obj):
            out = obj
            if isinstance(out, dict):
                out = {k:post_decode(v) for k,v in out.items()}
            elif isinstance(out, list):
                out = [post_decode(v) for v in out]
            if isinstance(out, dict) and '*' in out:
                clsname = out.pop('*')
                cls = decoders[clsname]
                out = cls(out.pop('**'))
            if isinstance(out, dict):
                out = {(k[2:] if k.startswith('**') else k):v for k,v in out.items()}
            return out
        
        return post_decode(obj)



class DiskDict:
    '''
    Holds a dictionary in disk (sqlite3) using a CustomJSON class for conversion
        Keys must be text.
        Values must support serialization with JSON.parse
    
    Supports indexing the keys of the objects
    '''
    
    def __init__(self, file=':memory:', JSON=None):
        self.connection = sqlite3.connect(file)
        
        self.connection.execute(f'''
            CREATE TABLE IF NOT EXISTS objects(
                key TEXT NOT NULL PRIMARY KEY,
                obj TEXT NOT NULL
            )
        ''')
        self.connection.execute('''
            CREATE TABLE IF NOT EXISTS indexed(
                key TEXT NOT NULL
            )
        ''')
        self.JSON = JSON or CustomJSON()
    
    def __iter__(self):
        q = (f'SELECT obj FROM objects',)
        yield from map(self.JSON.parse, self._column(*q))
    
    def __contains__(self, key):
        q = (f'SELECT key FROM objects WHERE key=?', (key,))
        yield any(k==key for k in self._column(*q))
    
    def __getitem__(self, key):
        q = (f'SELECT obj FROM objects WHERE key=?', (key,))
        found = list(map(self.JSON.parse, self._column(*q)))
        if not found:
            raise KeyError(key)
        return found.pop()
    
    @property
    def indexed(self):
        value = self.__dict__.get('__indexed')
        if value is None:
            value = self._get_columns('indexed')[1:]
            self.__dict__['__indexed'] = value
        return value
    
    def __setitem__(self, key, obj):
        pre_encoded, value = self.JSON._stringify(obj)
        if key in self:
            self._del_indexed(key)
        self._insert_indexed(((key, pre_encoded),))
        self._exec(f'REPLACE INTO objects VALUES (?,?)', (key, value))

    def _insert_indexed(self, items, table='indexed'):
        indexed = self.indexed if table=='indexed' else self._get_columns(table)[1:]
        qmark = ','.join('?' for key in indexed)
        query = f'INSERT INTO {table} VALUES (?,{qmark})'
        for key, obj in items:
            if hasattr(obj, 'get'):
                values = (obj.get(key) for key in indexed)
                self._exec(query, (key, *values))
    
    def get(self, key, default=None):
        q = (f'SELECT obj FROM objects WHERE key=?', (key,))
        return next(map(self.JSON.parse, self._column(*q)), default)
    
    def keys(self):
        return list(self)
    
    def _column(self, *q):
        it = (t for t,*_ in self.connection.execute(*q))
        yield from it
    
    def _exec(self, *q):
        self.connection.execute(*q)
        self.connection.commit()
    
    def __iter__(self):
        q = (f'SELECT key FROM objects',)
        yield from self._column(*q)
    
    def items(self):
        parse = self.JSON.parse
        it = self.connection.execute(f'SELECT key, obj FROM objects')
        yield from ((key, parse(value)) for key,value in it)
    
    def indexed_items(self):
        yield from self.connection.execute(f'SELECT * FROM indexed')
    
    def where_query(self, params):
        'Usage: see self.where'
        indexed = self.indexed
        values = []
        def parse(column, eq, value):
            if eq.lower() in ('and', 'or'):
                return f'({parse(*column)} {eq} {parse(*value)})'
            else:
                assert eq in ('==', '!=', '<','<=', '>', '>='), f'Invalid operator: {eq}'
                assert column in indexed, f'Can not run query on non-indexed column "{column}"'
                if value is None:
                    assert eq in ('==', '!='), f'Invalid operator with NULL: {eq}'
                    if eq=='==':
                        return f'({column} IS NULL)'
                    else:
                        return f'({column} IS NOT NULL)'
                else:
                    if eq=='!=':
                        eq='<>'
                    elif eq=='==':
                        eq='='
                    values.append(value)
                    return f'({column} {eq} ?)'
        return (f'SELECT key FROM indexed WHERE {parse(*params)}', values)
    
    def where(self, params):
        '''
        Usage:
            where((column, '<', value))
            where(((('n', '==', 3), 'and', ('k', '>=', 4)), 'or' ('name', '!=', 'carlos')))
        '''
        q = self.where_query(params)
        yield from (self[key] for key in self._column(*q))
    
    def __delitem__(self, key):
        self._exec(f'DELETE FROM objects WHERE key=?', (key,))
        self._del_indexed(key)
    
    def _del_indexed(self, key):
        self._exec(f'DELETE FROM indexed WHERE key=?', (key,))
    
    def del_index(self, column):
        assert column!='key'
        self._exec(f'CREATE TABLE tmp_indexed AS SELECT * FROM indexed WHERE 1=0')
        self._exec(f'ALTER TABLE tmp_indexed DROP COLUMN {column}')
        self._insert_indexed(self.items(), table='tmp_indexed')
        self._exec(f'ALTER TABLE indexed RENAME TO tmp__indexed')
        self._exec(f'ALTER TABLE tmp_indexed RENAME TO indexed')
        self._exec(f'DROP TABLE IF EXISTS tmp__indexed')
    
    def _get_columns(self, table):
        q = (f'SELECT name FROM PRAGMA_TABLE_INFO(?)', (table,))
        return list(self._column(*q))
    
    def __len__(self):
        return next(self._column(f'SELECT COUNT(key) FROM objects'))

    def add_index(self, column, sql_type):
        self._exec(f'DROP TABLE IF EXISTS tmp_indexed')
        self._exec(f'CREATE TABLE tmp_indexed AS SELECT * FROM indexed WHERE 1=0')
        self._exec(f'ALTER TABLE tmp_indexed ADD COLUMN {column} {sql_type}')
        self._insert_indexed(self.items(), table='tmp_indexed')
        self._exec(f'ALTER TABLE indexed RENAME TO tmp__indexed')
        self._exec(f'ALTER TABLE tmp_indexed RENAME TO indexed')
        self._exec(f'DROP TABLE IF EXISTS tmp__indexed')
        self.__dict__.pop('__indexed', None)
    

JSON = CustomJSON()
