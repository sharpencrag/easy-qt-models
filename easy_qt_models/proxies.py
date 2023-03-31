from contextlib import contextmanager
from typing import Callable, List, Optional, Any, Sequence
from easy_qt_models.base_collection import ModelRecord
from operator import lt

import easy_qt_models

from PySide2 import QtCore

# Type aliases
FilterFunc = Callable[[Any], bool]
SortFunc = Callable[[Any, Any], bool]


__all__ = ["EasySortFilterModel"]


class EasySortFilterModel(QtCore.QSortFilterProxyModel):
    """Creates a sort/filter proxy of a given model.

    Proxies can be sortable, filterable, or both.

    For filtering, users provide a filter_func which returns False for any item
    that should be removed from the proxy.

    Sorting uses python's default sorting algorithm on whatever the fields'
    sort_by attributes are set to.
    """

    def __init__(
        self,
        model: easy_qt_models.EasyModel,
        sortable: bool = True,
        filterable: bool = True,
        filter_func: Optional[FilterFunc] = None,
        sort_func: Optional[SortFunc] = None,
        parent: Optional[QtCore.QObject] = None,
    ):
        super().__init__(parent)
        self.source_model = model
        self.filterable = filterable
        self.sortable = sortable

        # Establish a default filter function for this instance if one is
        # not provided
        if filter_func is None:

            def truth(*args):
                return True

            self.filter_func = truth
        else:
            self.filter_func = filter_func

        self.sort_func = sort_func or lt

        self.collection = model.model_collection

        self.setDynamicSortFilter(True)
        self.setSourceModel(model)
        self.setSortRole(easy_qt_models.SORT_ROLE)
        self.setFilterRole(easy_qt_models.FILTER_ROLE)

    @property
    def record_indexes(self) -> List[QtCore.QModelIndex]:
        """Return all proxied indexes for all records in this model."""
        return self._record_indexes()

    def _record_indexes(self, parent=None) -> List[QtCore.QModelIndex]:
        """Recursively get all proxied indexes for this model."""
        parent = parent or easy_qt_models.get_invalid_index()
        row_count = self.rowCount(parent)
        indexes = [self.index(row_number, 0, parent) for row_number in range(row_count)]
        for index in indexes:
            indexes.extend(
                [
                    self.index(row_number, 0, index)
                    for row_number in range(self.rowCount(index))
                ]
            )
        return indexes

    def lessThan(
        self,
        left_source_index: QtCore.QModelIndex,
        right_source_index: QtCore.QModelIndex,
    ) -> bool:
        """Reimplementation: Qt calls this when sorting data in a view."""
        if not self.sortable:
            return False
        left_sort = self.source_model.data(left_source_index, self.sortRole())
        right_sort = self.source_model.data(right_source_index, self.sortRole())
        return self.sort_func(left_sort, right_sort)

    def filterAcceptsRow(
        self, row_number: int, parent_index: QtCore.QModelIndex
    ) -> bool:
        """Reimplementation: Called by Qt when filtering data in a view."""
        if not self.filterable:
            return True
        filter_record = self.get_record_to_filter(row_number, parent_index)
        column_number = self.filterKeyColumn()
        return self.filter_func(filter_record.data(column_number, self.filterRole()))

    def get_record_to_filter(
        self, row_number: int, parent_index: QtCore.QModelIndex
    ) -> ModelRecord:
        """Return the record that should be filtered for the row."""
        parent_record = parent_index.internalPointer() or self.collection
        return parent_record.child_records[row_number]

    def source_index(self, index: QtCore.QModelIndex) -> QtCore.QModelIndex:
        """Return the source index for a given proxy index."""
        return self.mapToSource(index)

    def field_at_index(self, index: QtCore.QModelIndex) -> easy_qt_models.ModelField:
        """Return the ModelField in the source model for a given proxy index."""
        return self.source_model.field_at_index(self.source_index(index))

    @contextmanager
    def layout_change_ctx(self):
        """Context manager for model changes altering the shape of the model."""
        with self.source_model.layout_change_ctx():
            yield

    @contextmanager
    def model_reset_ctx(self):
        """Context manager for model resets"""
        with self.source_model.reset_ctx():
            yield

    @contextmanager
    def data_change_ctx(self):
        """Context manager for model changes that only update data."""
        with self.source_model.data_change_ctx():
            yield
        self.sort_cache = {}

    @contextmanager
    def insert_rows_ctx(
        self,
        parent: QtCore.QModelIndex,
        start: int,
        row_sequence: Sequence[ModelRecord],
    ):
        """Context manager for inserting rows into the model.

        This method is provided for completeness, but the layout_change_ctx
        context manager should be used instead in most cases.
        """
        with self.source_model.insert_rows_ctx(parent, start, row_sequence):
            yield

    @contextmanager
    def remove_rows_ctx(
        self,
        parent: QtCore.QModelIndex,
        start: int,
        row_sequence: Sequence[ModelRecord],
    ):
        """Context manager for removing rows from the model.

        This method is provided for completeness, but the layout_change_ctx
        context manager should be used instead in most cases.
        """
        with self.source_model.remove_rows_ctx(parent, start, row_sequence):
            yield

    def data(self, index: QtCore.QModelIndex, role: int):
        """Interface to the data function on the source model"""
        return self.source_model.data(self.source_index(index), role)

    def headerData(
        self,
        column_number: int,
        orientation: QtCore.Qt.Orientation,
        role=QtCore.Qt.DisplayRole,
    ):
        """Interface to the header data on the source model.

        By default, this will always be a one-to-one mapping.  If a subclassing
        proxy model reorders columns, it may need to reimplement this method in
        order to accurately reflect the headers for the proxy
        """
        return self.source_model.headerData(column_number, orientation, role)
