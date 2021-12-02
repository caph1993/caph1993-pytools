from __future__ import annotations
from typing import Dict, List, Optional, cast
from random import shuffle
from .database import SqliteDB, FilePath, custom_repr
from .query import TableQuery


class SqliteTable(TableQuery):
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

    def __init__(self, file: FilePath, table_name: str):
        self.file = file
        self.name = table_name
        self.db = SqliteDB(self.file)

    def __repr__(self):
        return custom_repr(self, 'file', 'table_name')

    def __len__(self):
        return self.count()

    def columns(self) -> List[str]:
        query_str = 'SELECT name FROM PRAGMA_TABLE_INFO(?)'
        column_names = self.db.execute_column(
            query_str,
            [self.name],
        )
        column_names = cast(List[str], column_names)
        return column_names


def test():
    import random
    table = SqliteTable('.test.db', 'rand_table')
    table.db.execute(f'''
        CREATE TABLE IF NOT EXISTS rand_table(
            key int NOT NULL PRIMARY KEY,
            age int NOT NULL,
            prob double NOT NULL
        )
    ''')

    print(len(table))
    for k in set(range(1000)).difference(set(table.column('key'))):
        table.insert(
            key=k,
            age=random.randint(0, 5),
            prob=round(random.random(), 3),
        )
    print(table.random_dicts(3))
    print(table.random_dicts(3))
    print(len(table))
