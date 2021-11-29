import sqlite3
from typing import TYPE_CHECKING, Generic, TypeVar, Dict, List, Optional, cast
from .table import SqliteTable, Record, Columns, Data
from .queries import WhereClause, OrderBy
'''
Type declaration for several methods in table.py
Just replace from it
    **kw
with
    complex_where: WhereClause = None,
    order_by: OrderBy = None,
    limit: int = None,
    **where: Data
except for:
    value, dict, get_dict do not admit limit (forced to 1)
    random require non null limit
'''

F = TypeVar('F')


class copy(Generic[F]):

    def __init__(self, _: F) -> None:
        ...

    def __call__(self, wrapped) -> F:
        return wrapped


def _dicts(
    self: SqliteTable,
    *columns: str,
    complex_where: WhereClause = None,
    order_by: OrderBy = None,
    limit: int = None,
    **where: Data,
) -> List[Record]:
    ...


dicts = copy(_dicts)


def _column(
    self: SqliteTable,
    column: str,
    complex_where: WhereClause = None,
    order_by: OrderBy = None,
    limit: int = None,
    **where: Data,
) -> List[Data]:
    ...


column = copy(_column)


def _series(
    self: SqliteTable,
    *columns: str,
    complex_where: WhereClause = None,
    order_by: OrderBy = None,
    limit: int = None,
    **where: Data,
) -> Dict[str, List[Data]]:
    ...


series = copy(_series)


def _rows(
    self: SqliteTable,
    *columns: str,
    complex_where: WhereClause = None,
    order_by: OrderBy = None,
    limit: int = None,
    **where: Data,
) -> List[List[Data]]:
    ...


rows = copy(_rows)


def _dict(
    self: SqliteTable,
    *columns: str,
    complex_where: WhereClause = None,
    **where: Data,
) -> Record:
    ...


dict = copy(_dict)


def _get_dict(
    self: SqliteTable,
    *columns: str,
    complex_where: WhereClause = None,
    **where: Data,
) -> Optional[Record]:
    ...


get_dict = copy(_get_dict)


def _value(
    self: SqliteTable,
    column: str,
    complex_where: WhereClause = None,
    **where: Data,
) -> Data:
    ...


value = copy(_value)


def _get_value(
    self: SqliteTable,
    column: str,
    complex_where: WhereClause = None,
    **where: Data,
) -> Optional[Data]:
    ...


get_value = copy(_get_value)


def _count(
    self: SqliteTable,
    complex_where: WhereClause = None,
    limit: int = None,
    **where: Data,
) -> int:
    ...


count = copy(_count)


def _delete(
    self: SqliteTable,
    complex_where: WhereClause = None,
    limit: int = None,
    **where: Data,
) -> int:
    ...


delete = copy(_delete)


def _update_or_ignore(
    self: SqliteTable,
    partial_record: Record,
    complex_where: WhereClause = None,
    order_by: OrderBy = None,
    limit: int = None,
    **where: Data,
) -> int:
    ...


update_or_ignore = copy(_update_or_ignore)


def _update(
    self: SqliteTable,
    partial_record: Record,
    complex_where: WhereClause = None,
    order_by: OrderBy = None,
    limit: int = None,
    **where: Data,
) -> None:
    ...


update = copy(_update)


def _random_dict(
    self: SqliteTable,
    *columns: str,
    complex_where: WhereClause = None,
    **where: Data,
) -> Record:
    ...


random_dict = copy(_random_dict)


def _random_dicts(
    self: SqliteTable,
    *columns: str,
    limit: int,
    complex_where: WhereClause = None,
    **where: Data,
) -> List[Record]:
    ...


random_dicts = copy(_random_dicts)


def _random_rows(
    self: SqliteTable,
    *columns: str,
    limit: int,
    complex_where: WhereClause = None,
    **where: Data,
) -> List[List[Data]]:
    ...


random_rows = copy(_random_rows)
