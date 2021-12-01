from __future__ import annotations
from pathlib import Path
import sqlite3
#from sqlite3.dbapi2 import ProgrammingError
from typing import List, Any, Tuple, Union, cast
from pathlib import Path
from .types import (
    Data,
    Params,
)

FilePath = Union[str, Path]


def custom_repr(self, *keys):
    name = self.__class__.__name__
    comma_kwargs = ', '.join(f'{k}={repr(getattr(self, k))}' for k in keys)
    return f'{name}({comma_kwargs})'


class SqliteDB:
    '''
    '''

    def __init__(self, file: FilePath):
        self.file = file

    def __repr__(self):
        return custom_repr(self, 'file')

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

    def execute(self, query: str, params: Params = None) -> List[List[Data]]:
        return [*self._execute(query, params or [])]

    def execute_column(self, query: str, params: Params = None) -> List[Data]:
        rows = self.execute(query, params)
        return [first for first, *_ in rows]

    def get_table(self, table_name: str):
        from .table import SqliteTable
        return SqliteTable(self.file, table_name)

    def table_names(self) -> List[str]:
        table_names = self.execute_column("""
            SELECT name FROM sqlite_master 
            WHERE type = 'table' 
            AND name NOT LIKE 'sqlite_%'
            ORDER BY 1;
        """)
        table_names = cast(List[str], table_names)
        return table_names

    def index_names(self):
        return self.execute_column("""
            SELECT name FROM sqlite_master 
            WHERE type = 'index' 
            ORDER BY 1;
        """)
