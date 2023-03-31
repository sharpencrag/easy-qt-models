from contextlib import contextmanager
import uuid
from typing import Optional, List, Callable, Sequence, Union, Any, Dict, TypeVar

from PySide2 import QtCore
from PySide2.QtCore import Qt

from easy_qt_models.base_collection import ModelField, ModelRecord, ModelCollection

# type alias for better annotation
ModelRole = Union[int, QtCore.Qt.ItemDataRole]


__all__ = [
    "EasyModel",
    "get_invalid_index",
    "field_at_index",
    "record_at_index",
    "data_at_index",
    "locate_index",
]


class EasyModel(QtCore.QAbstractItemModel):
    """Qt model built around using ModelCollection as a data source.

    *  all functions assume we're using ModelCollections as our data source
    *  all data() calls are pushed to ModelField, which handles
       the data roles using normal python attributes and properties.

    Generally, users will subclass ModelField to create a custom interface
    for their data. See the ModelField class definition for more info.
    """

    # Stores the record when drag-and-dropping
    _temp_record_stash = {}

    # Stores references to unused records.  This is due to a toxic combination
    # of C++ pointers and python garbage collection.  In some very rare cases,
    # a record will be deleted by python, but the C++ pointer for the index
    # will still be valid.  This causes either a crash or bizarre behavior.
    # THIS SOLUTION IS A MEMORY LEAK.
    # TODO: find a better solution for this, or root out the bug
    _persistent_record_stash = {}

    # A mimetype is required for drag and drop operations.
    drag_drop_mimetype = "application/x-drag-drop-record"

    def __init__(
        self,
        model_collection: ModelCollection,
        drop_enabled: bool = True,
        parent: Optional[QtCore.QObject] = None,
    ):
        super(EasyModel, self).__init__(parent=parent)
        self.model_collection = model_collection
        self.drop_enabled = drop_enabled

        # the application name will be provided when items are dragged
        # and dropped from item views using this model. This attribute MUST
        # be a string
        self.application_name: str = "EasyModel"

    def hasIndex(
        self, row_number: int, column_number: int, parent: Optional[ModelRecord] = None
    ) -> bool:
        """Reimpl: If an item at the given row / column exists, return True."""
        parent = parent or get_invalid_index()
        parent_record = record_at_index(parent) or self.model_collection

        try:
            parent_record.child_records[row_number].fields[column_number]
        except IndexError:
            return False
        else:
            return True

    def index(
        self,
        row_number: int,
        column_number: int,
        parent: Optional[QtCore.QModelIndex] = None,
    ) -> QtCore.QModelIndex:
        """Reimplementation: create a new index for the given coordinate and parent."""
        parent = parent or get_invalid_index()
        if not self.hasIndex(row_number, column_number, parent):
            return get_invalid_index()
        parent_record = record_at_index(parent) or self.model_collection
        if parent_record is None:
            return get_invalid_index()
        record = parent_record.child_records[row_number]
        return self.createIndex(row_number, column_number, record)

    def make_record_indexes(
        self, parent: Optional[QtCore.QModelIndex] = None
    ) -> List[QtCore.QModelIndex]:
        """Generate indexes for all direct child records of the given parent index."""
        parent = parent or get_invalid_index()
        row_count = self.rowCount(parent)
        return [self.index(record, 0, parent) for record in range(row_count)]

    def make_record_indexes_recursive(
        self, parent: Optional[QtCore.QModelIndex] = None
    ):
        """Recursively generate indexes for all descendants of the given parent index"""
        parent = parent or get_invalid_index()
        all_indexes = self.make_record_indexes(parent=parent)
        for index in all_indexes:
            # NOTE: we always use the zeroeth column to define hierarchies by convention
            all_indexes.extend(
                [
                    self.index(row_number, 0, index)
                    for row_number in range(self.rowCount(index))
                ]
            )
        return all_indexes

    def hasChildren(self, parent: Optional[QtCore.QModelIndex] = None) -> bool:
        """Reimplementation: Return True if this record has children."""
        parent_record = record_at_index(parent) or self.model_collection
        return bool(parent_record.child_records)

    def parent(self, index: QtCore.QModelIndex) -> QtCore.QModelIndex:
        """Reimplementation: return the parent index of the given index"""
        if not index.isValid():
            return get_invalid_index()

        record = record_at_index(index)

        if record is None:
            return get_invalid_index()

        try:
            parent_record = record.parent
        except AttributeError:
            return get_invalid_index()
        if parent_record is None:
            return get_invalid_index()

        try:
            grandparent_record = parent_record.parent or self.model_collection
        except AttributeError:
            return get_invalid_index()
        row_number = grandparent_record.child_records.index(parent_record)

        # NOTE: hierarchies are determined by the zeroeth column by convention
        return self.createIndex(row_number, 0, parent_record)

    def bottom_right_index(
        self, parent: Optional[QtCore.QModelIndex] = None
    ) -> QtCore.QModelIndex:
        """Helper: Returns the bottom-rightmost index of the model.

        This is used to gracefully update the entire model when data changes
        occur. This is a recursive function that will be called until the given
        parent has no more children.
        """
        parent = parent or self.model_collection
        bottom_record = parent.child_records[-1]

        child_records = bottom_record.child_records

        if child_records:
            # recurse with the child record as the new parent to search
            return self.bottom_right_index(bottom_record)

        # when no more children are found, assume this is the bottom-most
        # record in the collection.  In order to update all fields, we need
        # the right-most field index of this bottom-most record (last column,
        # last row)
        return self.createIndex(
            len(child_records), len(bottom_record.fields), bottom_record
        )

    def rowCount(self, parent: Optional[QtCore.QModelIndex] = None) -> int:
        """Reimplementation: the current number of records in a particular parent context"""
        parent = parent or get_invalid_index()
        parent_record = record_at_index(parent) or self.model_collection
        return len(parent_record.child_records)

    def columnCount(self, parent: Optional[QtCore.QModelIndex] = None) -> int:
        """Reimplementation: the number total columns in the model"""
        parent = parent or get_invalid_index()
        return self.model_collection.column_count

    def sort(self, column_number: int, direction=Qt.AscendingOrder):
        """Reimplementation: sort the model by sorting each child record (row) in turn"""
        if direction == Qt.AscendingOrder:
            reverse = False
        else:
            reverse = True

        with self.layout_change_ctx():
            self.model_collection.sort_in_place(column_number, reverse=reverse)

    # NOTE: in order to support drag and drop on the model level, we have to
    #       reimplement supportedDropActions, mimeData, dropMimeData, mimeTypes,
    #       removeRows and insertRows.  See the docstrings for these methods to
    #       get a better idea of how drag-and-drop operations work.

    def supportedDropActions(self):
        """Reimplementation: Only enable Move Actions

        We only support MoveAction operations when drag-and-drop is enabled.
        This will remove a given item and insert it into a model at the
        user-specified drop point.
        """

        if self.drop_enabled:
            return Qt.MoveAction
        return Qt.IgnoreAction

    def removeRows(
        self,
        row_number: int,
        row_count: int,
        parent: Optional[QtCore.QModelIndex] = None,
    ):
        """Reimplementation: Remove one or more rows from the model.

        This method is called when a user initiates a drag-and-drop MoveAction
        operation.  The selected rows get removed from the model and the
        underlying model collection entirely.

        When the "drop" event occurs, the records are re-inserted into the
        model collection at the user-specified drop point.
        """

        # skip any invalid rows
        if (
            row_number < 0
            or row_count < 1
            or (row_number + row_count) > self.rowCount(parent)
        ):
            return False

        parent_index = parent or get_invalid_index()
        parent_record = record_at_index(parent_index) or self.model_collection

        remove_start = row_number
        remove_end = row_number + row_count
        remove_end_exclusive = remove_end - 1

        self.beginRemoveRows(parent, remove_start, remove_end_exclusive)

        for row_number in range(remove_start, remove_end):
            child_record = parent_record.child_records[row_number]
            self.model_collection.remove_record(child_record)
            self._persistent_record_stash[id(child_record)] = child_record

        self.endRemoveRows()

        return True

    def insert_records(
        self,
        records: List[ModelRecord],
        position: int,
        parent: Optional[QtCore.QModelIndex] = None,
    ) -> bool:
        """Insert records under the given parent index at the given position."""
        if not parent or not parent.isValid():
            parent = get_invalid_index()
            parent_record = None
        else:
            parent_record = record_at_index(parent)

        insert_to = (position + len(records)) - 1

        self.beginInsertRows(parent, position, insert_to)

        for position, record in enumerate(records, start=position):
            self.model_collection.insert_record(position, record, parent=parent_record)
        self.endInsertRows()

        return True

    def mimeData(self, indexes: List[QtCore.QModelIndex]):
        """Reimplementation: Serialize data to enable drag-and-drop."""
        records = list(set([record_at_index(index) for index in indexes]))

        # raise an exception if any of the retrieved items aren't ModelRecords
        for record in records:
            if not isinstance(record, ModelRecord):
                raise TypeError("record is not a ModelRecord: {}".format(record))

        uuid_ = str(uuid.uuid1())
        self._temp_record_stash[uuid_] = records
        mime_data = QtCore.QMimeData()
        mime_data.setData(self.drag_drop_mimetype, bytes(uuid_, encoding="utf-8"))
        return mime_data

    def mimeTypes(self):
        """Reimplementation: List of mime-types that this model will generate.

        This is only necessary for drag-and-drop operations.
        """
        return [self.drag_drop_mimetype]

    def dropMimeData(
        self,
        data: QtCore.QMimeData,
        _,
        row: int,
        column: int,
        parent: QtCore.QModelIndex,
    ) -> bool:
        """Reimplementation: Retrieve data and insert it into the model."""
        if row == -1 and column == -1:
            row = self.rowCount(parent)
        mime_data = str(data.data(self.drag_drop_mimetype), encoding="utf-8")
        records = self._temp_record_stash.pop(mime_data)
        records = [record.copy() for record in records]
        self.insert_records(records, row, parent)
        return True

    def filter(self, column_number: int, filter_func: Callable):
        """Filter in-place by applying filter_func to Fields in the given column."""
        with self.layout_change_ctx():
            self.model_collection.filter_in_place(column_number, filter_func)

    def flags(self, index: QtCore.QModelIndex) -> Qt.ItemFlags:
        """Reimplementation: Returns item flags bitmask for the given index.

        Item flags are used to determine which operations are allowed on a
        given item.  For example, if an item is selectable, enabled, or
        editable.
        """
        flags = Qt.NoItemFlags
        if not index.isValid():
            return flags | Qt.ItemIsDropEnabled
        field = self.field_at_index(index)
        if field.selectable:
            flags |= Qt.ItemIsSelectable
        if field.editable:
            flags |= Qt.ItemIsEditable
        if field.drag_enabled:
            flags |= Qt.ItemIsDragEnabled
        if field.drop_enabled:
            flags |= Qt.ItemIsDropEnabled
        if field.checkable:
            flags |= Qt.ItemIsUserCheckable
        if field.enabled:
            flags |= Qt.ItemIsEnabled
        if field.tristate:
            flags |= Qt.ItemIsTristate
        return flags

    @contextmanager
    def reset_ctx(self):
        """Context Manager: Use when the entire model needs to be reset.

        Usage:
            with model.reset_ctx():
                ... make changes ...
        """
        self.beginResetModel()
        yield
        self.endResetModel()

    @contextmanager
    def layout_change_ctx(self):
        """Context Manager: Use when the layout of the model will be changed.

        This might be due to adding, removing, or re-ordering records.

        Usage:
            with model.layout_change_ctx():
                ... make changes ...
        """
        self.layoutAboutToBeChanged.emit()
        yield
        self.layoutChanged.emit()

    @contextmanager
    def insert_rows_ctx(
        self,
        parent: QtCore.QModelIndex,
        start: int,
        row_sequence: Sequence[ModelRecord],
    ):
        """Context Manager: Use when inserting an iterable of records.

        NOTE: it is almost always easier and safer to use layout_change_ctx
              instead, it will do exactly the same thing without needing a
              parent and position
        """
        self.beginInsertRows(parent, start, (start + len(row_sequence)))
        yield
        self.endInsertRows()

    @contextmanager
    def remove_rows_ctx(
        self,
        parent: QtCore.QModelIndex,
        start: int,
        row_sequence: Sequence[ModelRecord],
    ):
        """Context Manager: Use when removing an iterable of records.

        NOTE: it is almost always easier and safer to use layout_change_ctx
              instead of remove_rows_ctx, it will do exactly the same thing
              without needing a parent and position
        """
        self.beginRemoveRows(parent, start, (start + len(row_sequence)))
        yield
        self.endRemoveRows()

    @contextmanager
    def data_changed_ctx(self):
        """Context Manager: Use for non-layout changes to the user data."""
        yield
        top_left = self.createIndex(0, 0, record_at_index(self.index(0, 0)))
        self.dataChanged.emit(top_left, self.bottom_right_index())

    @staticmethod
    def record_at_index(index: QtCore.QModelIndex) -> Union[ModelRecord, None]:
        """Interface to the module-level record_at_index function"""
        return record_at_index(index)

    def field_at_index(self, index: QtCore.QModelIndex) -> ModelField:
        """Retrieve the underlying user data Field at a given index.

        If the item does not exist, return a blank ModelField.
        """
        default_field = ModelField("")

        data_record = record_at_index(index)
        if data_record is None:
            return default_field
        parent_record = data_record.parent or self.model_collection

        row_number = index.row()
        column_number = index.column()

        try:
            return parent_record.child_records[row_number].fields[column_number]
        except IndexError:
            return default_field

    def data(self, index: QtCore.QModelIndex, role: ModelRole) -> Any:
        """Reimplementation - retrieve the data for the given index and role.

        Data lookups happen like this.
            A Qt Item View asks for data from the model ->
            QtBaseModel pushes that request to its ModelCollection ->
            ModelCollection pushes that request to the correct ModelRecord ->
            ModelRecord pushes that request to the correct ModelField ->
            ModelField calls its data() method and returns the correct data
        """
        record = record_at_index(index)
        if record is None:
            return None
        return record.data(index.column(), role)

    def setData(self, index: QtCore.QModelIndex, value: Any, role: ModelRole):
        """Reimplementation: set the data for the given index and role"""
        record = record_at_index(index)
        if record is None:
            return
        record.set_data(index.column(), value, role)
        self.dataChanged.emit(index, index)

    def headerData(
        self, column_number: int, orientation: Qt.Orientation, role: ModelRole
    ):
        """Reimplementation: Return the header label for the column.

        If no header data exists, return an empty string.

        NOTE: right now we only support the display role for headers, and
              defer all other roles to the superclass.  Eventually we may
              be able to support decorations and other kinds of roles.
        """
        if role != Qt.DisplayRole:
            return super().headerData(column_number, orientation, role)
        try:
            return self.model_collection.header_labels[column_number]
        except:
            return ""


def field_at_index(index: QtCore.QModelIndex) -> Optional[ModelField]:
    """Get the ModelField at the given index"""
    return index.model().field_at_index(index)


def data_at_index(index: QtCore.QModelIndex) -> Any:
    """Returns the underlying user data object in the ModelField for the index."""
    field = field_at_index(index)
    if field is None:
        return None
    return field.user_data


def record_at_index(index: Optional[QtCore.QModelIndex]) -> Optional[ModelRecord]:
    """Retrieve the ModelRecord for the given index."""
    try:
        # if the model is a proxy model, we need to map the index to the source
        return index.model().mapToSource(index).internalPointer()
    except AttributeError:
        return index.internalPointer()


def locate_index(
    model: EasyModel,
    locator_func: Callable,
    parent: Optional[QtCore.QModelIndex] = None,
):
    """Return the first index for which locator_func returns True"""
    check_indexes = list()
    invalid_index = get_invalid_index()
    parent = parent or invalid_index
    rows = range(model.rowCount(parent))
    for row in rows:
        idx = model.index(row, 0, parent)
        if idx == invalid_index:
            continue
        if locator_func(idx):
            return idx
        check_indexes.append(idx)
    for idx in check_indexes:
        ret_idx = locate_index(model, locator_func, idx)
        if ret_idx is not None:
            return ret_idx


def get_invalid_index() -> QtCore.QModelIndex:
    """Return the invalid index.

    Invalid indexes are used as placeholders for non-existent parts of the
    model, including the root "node" of the model.

    Because this happens so often, we memoize the invalid index to avoid
    creating a new one every time we need it.
    """
    memo: Dict[str, Optional[QtCore.QModelIndex]]
    memo = {"idx": None}

    def _get_invalid_index():
        invalid_index = memo["idx"]
        if invalid_index is None:
            invalid_index = QtCore.QModelIndex()
            memo["idx"] = invalid_index
        return invalid_index

    return _get_invalid_index()
