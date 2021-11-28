import sqlite3
from typing import TYPE_CHECKING, Generic, TypeVar, Dict, List, Optional, cast
from .table import SqliteTable, Record, Columns, Data
from .queries import WhereClause, OrderBy
'''
Type declaration for several methods in table.py
Just replace from it
    **kw
with
    where: WhereClause = None,
    order_by: OrderBy = None,
    limit: int = None,
    **where_equal: Data
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
    where: WhereClause = None,
    order_by: OrderBy = None,
    limit: int = None,
    **where_equal: Data,
) -> List[Record]:
    ...


dicts = copy(_dicts)


def _column(
    self: SqliteTable,
    column: str,
    where: WhereClause = None,
    order_by: OrderBy = None,
    limit: int = None,
    **where_equal: Data,
) -> List[Data]:
    ...


column = copy(_column)


def _series(
    self: SqliteTable,
    *columns: str,
    where: WhereClause = None,
    order_by: OrderBy = None,
    limit: int = None,
    **where_equal: Data,
) -> Dict[str, List[Data]]:
    ...


series = copy(_series)


def _rows(
    self: SqliteTable,
    *columns: str,
    where: WhereClause = None,
    order_by: OrderBy = None,
    limit: int = None,
    **where_equal: Data,
) -> List[List[Data]]:
    ...


rows = copy(_rows)


def _dict(
    self: SqliteTable,
    *columns: str,
    where: WhereClause = None,
    order_by: OrderBy = None,
    limit: int = None,
    **where_equal: Data,
) -> Record:
    ...


dict = copy(_dict)


def _get_dict(
    self: SqliteTable,
    *columns: str,
    where: WhereClause = None,
    order_by: OrderBy = None,
    limit: int = None,
    **where_equal: Data,
) -> Optional[Record]:
    ...


get_dict = copy(_get_dict)


def _value(
    self: SqliteTable,
    column: str,
    where: WhereClause = None,
    order_by: OrderBy = None,
    limit: int = None,
    **where_equal: Data,
) -> Data:
    ...


value = copy(_value)


def _get_value(
    self: SqliteTable,
    column: str,
    where: WhereClause = None,
    order_by: OrderBy = None,
    limit: int = None,
    **where_equal: Data,
) -> Optional[Data]:
    ...


get_value = copy(_get_value)


def _count(
    self: SqliteTable,
    where: WhereClause = None,
    order_by: OrderBy = None,
    limit: int = None,
    **where_equal: Data,
) -> int:
    ...


count = copy(_count)


def _delete(
    self: SqliteTable,
    where: WhereClause = None,
    order_by: OrderBy = None,
    limit: int = None,
    **where_equal: Data,
) -> int:
    ...


delete = copy(_delete)


def _update_or_ignore(
    self: SqliteTable,
    partial_record: Record,
    where: WhereClause = None,
    order_by: OrderBy = None,
    limit: int = None,
    **where_equal: Data,
) -> int:
    ...


update_or_ignore = copy(_update_or_ignore)


def _update(
    self: SqliteTable,
    partial_record: Record,
    where: WhereClause = None,
    order_by: OrderBy = None,
    limit: int = None,
    **where_equal: Data,
) -> None:
    ...


update = copy(_update)
