import typing as t
import uuid

from PySide2 import QtCore, QtGui, QtWidgets
from PySide2.QtCore import Qt

# convenience type alias for better annotations
ModelRole = int


__all__ = [
    "ModelField",
    "ModelRecord",
    "ModelCollection",
    "FromAttr",
    "FromCallback",
    "WidgetFactory",
    "USER_DATA_ROLE",
    "SORT_ROLE",
    "FILTER_ROLE",
    "QT_ROLE_MAP",
]


USER_DATA_ROLE = 256

SORT_ROLE = 257

FILTER_ROLE = 258

#: Maps nice pythonic names to the Qt.ItemDataRole enumerators
QT_ROLE_MAP = {
    Qt.DisplayRole: "display",
    Qt.DecorationRole: "decoration",
    Qt.EditRole: "edit",
    Qt.ToolTipRole: "tool_tip",
    Qt.StatusTipRole: "status_tip",
    Qt.WhatsThisRole: "whats_this",
    Qt.SizeHintRole: "size_hint",
    Qt.FontRole: "font",
    Qt.TextAlignmentRole: "alignment",
    Qt.BackgroundRole: "background",
    Qt.ForegroundRole: "foreground",
    Qt.CheckStateRole: "checkstate",
    Qt.InitialSortOrderRole: "default_sort_order",
    Qt.AccessibleDescriptionRole: "accessible_desc",
    Qt.AccessibleTextRole: "accessible_text",
    USER_DATA_ROLE: "user_data",
    SORT_ROLE: "sort_by",
    FILTER_ROLE: "filter_by",
}


class FromAttr:
    header_label: t.Optional[str] = None

    def __init__(self, attr_name: str):
        """Maps an attribute name to a Qt role.

        This class can be used when defining both Fields and Records::

            user = User(name="John", age=25)

            class MyField(ModelField):
                display = FromAttr("name")  # <- displays "John"

            class MyRecord(ModelRecord):
                fields = [MyField, FromAttr("age")] # <- John | 25
        """
        self.attr_name = attr_name


class FromCallback:
    """Maps a callback to a Qt role.

    This class can be used when defining both Fields and Records::

        user = User(name="Ron", age=25)

        class MyField(ModelField):
            display = FromCallback(lambda u: u.name.upper())  # <- "RON"

        class MyRecord(ModelRecord):
            fields = [MyField, FromCallback(lambda u: u.age + 1)] # <- RON | 26
    """

    header_label: t.Optional[str] = None

    def __init__(self, callback: t.Callable, *args, **kwargs):
        self.callback = callback
        self.args = args
        self.kwargs = kwargs


class WidgetFactory:
    def __init__(self, widget_type: t.Type[QtWidgets.QWidget], *args, **kwargs):
        """Provides a mechanism for creating a widget for a field.

        Note that widget hints set on ModelFields do not do anything on their
        own, they must be populated as part of the view code.
        """
        self.widget_type = widget_type
        self.args = args
        self.kwargs = kwargs

    def make_widget(self, user_data: t.Any):
        """Returns a new widget for the given user data.

        This method should be called by view code to populate a tree or table
        view with widgets.
        """
        return self.widget_type(user_data, *self.args, **self.kwargs)


class _Roles:
    """Provides type annotations for ModelField and ModelRecord."""

    display: t.Union[str, FromAttr, FromCallback]
    decoration: t.Union[
        QtGui.QColor, QtGui.QIcon, QtGui.QPixmap, FromAttr, FromCallback
    ]
    edit: t.Union[str, FromAttr, FromCallback]
    tool_tip: t.Union[str, FromAttr, FromCallback]
    status_tip: t.Union[str, FromAttr, FromCallback]
    whats_this: t.Union[str, FromAttr, FromCallback]
    size_hint: t.Union[t.Tuple[int, int], QtCore.QSize, FromAttr, FromCallback]
    font: t.Union[QtGui.QFont, FromAttr, FromCallback]
    alignment: t.Union[Qt.AlignmentFlag, FromAttr, FromCallback]
    background: t.Union[QtGui.QBrush, FromAttr, FromCallback]
    foreground: t.Union[QtGui.QBrush, FromAttr, FromCallback]
    checkstate: t.Union[None, Qt.CheckState, FromAttr, FromCallback]
    default_sort_order: t.Union[Qt.SortOrder, FromAttr, FromCallback]
    accessible_description: t.Union[str, FromAttr, FromCallback]
    accessible_text: t.Union[str, FromAttr, FromCallback]
    user_data: t.Union[t.Any, FromAttr, FromCallback]
    sort_by: t.Union[t.Any, FromAttr, FromCallback]
    filter_by: t.Union[t.Any, FromAttr, FromCallback]


class ModelField(_Roles):
    """Provides a wrapper to user data which will be used in Qt models.

    Think of ModelField as a single 'cell' of data in a spreadsheet. Each
    Role attribute (defined in the Roles class) corresponds to a Qt role.
    For example, the 'display' attribute corresponds to the Qt.DisplayRole.

    ModelFields also have Flag attributes, which are used to set some features
    of Qt view items, like editability, checkability, and drag/drop support.

    ModelField attributes can be set to a value, a mapped attribute name, or
    a callback.  You can also define python properties for dynamic values.

    Finally, you can also specify a widget_hint, which is a widget type or
    a factory function that can be used by the view to replace the cell's
    contents with a widget.
    """

    # An optional label for the column header, if one is visible. If no
    # header_label is provided, no label will be shown.
    header_label: t.Optional[str] = None

    # Flags
    # these are default values for ItemStateFlags
    checkable: bool = False
    enabled: bool = True
    selectable: bool = True
    editable: bool = False
    drag_enabled: bool = False
    drop_enabled: bool = False
    tristate: bool = False

    # widget attributes
    widget_hint: t.Optional[t.Union[t.Type[QtWidgets.QWidget], WidgetFactory]] = None

    def __init__(self, user_data: t.Any, **attrs):
        """Args:

        user_data: The underlying business data that we want to display.

        **attrs: Any attributes that you want to set on the ModelField.
            These attributes should be one of the named attributes in the
            Roles class.
        """
        super(ModelField, self).__init__()
        self.user_data = user_data
        self.__dict__.update(attrs)
        self._set_fallbacks(user_data)

    def _set_fallbacks(self, user_data: t.Any):
        """Sets reasonable fallback values for some roles.

        If the user has not defined a value for the display, sort_by,
        filter_by, or edit attributes, provides a reasonable default.
        """
        try:
            user_data_as_string = str(user_data)
        except Exception:
            user_data_as_string = repr(user_data)

        if hasattr(self, "display"):
            if not hasattr(self, "sort_by"):
                self.sort_by = self.display
            if not hasattr(self, "filter_by"):
                self.filter_by = self.display
            if not hasattr(self, "edit"):
                self.edit = self.display
            if self.header_label is None and isinstance(self.display, FromAttr):
                self.header_label = self.display.attr_name
        else:
            self.display = user_data_as_string
            self.sort_by = user_data_as_string
            self.filter_by = user_data_as_string

    def data(self, qt_role: ModelRole):
        """Returns the view data for the ModelField, given a Qt role.

        Refer to the QT_ROLE_MAP dictionary for a complete mapping between the
        Qt.ItemDataRole enumerators and ModelField attributes.
        """

        try:
            role_attr = QT_ROLE_MAP[qt_role]
        except KeyError:
            return None
        value = getattr(self, role_attr, None)
        if isinstance(value, FromAttr):
            return getattr(self.user_data, value.attr_name)
        elif isinstance(value, FromCallback):
            return value.callback(*value.args, **value.kwargs)
        else:
            return value

    def set_data(self, value: t.Any, qt_role: ModelRole):
        """Attempts to set the data for both the ModelField and the user data.

        ModelField subclasses should re-implement this method if
            A) data editing is supported
            B) this implementation does not work for the user data provided
        """
        try:
            role_attr = QT_ROLE_MAP[qt_role]
        except KeyError:
            return False
        value = getattr(self, role_attr)
        if isinstance(value, FromAttr):
            setattr(self.user_data, value.attr_name, value)
        elif isinstance(value, FromCallback):
            raise NotImplementedError("Cannot set data on a callback!")

    def __repr__(self):
        hex_id = hex(id(self))
        return '<{class_name} object: "{display_value}" at {hex_id}>' "".format(
            class_name=self.__class__.__name__,
            display_value=self.display,
            hex_id=hex_id,
        )


class ModelRecord:
    """Provides a multi-column data record for use in Qt models.

    Think of ModelRecord as a single row of data in a spreadsheet. Each column
    of data is represented by a ModelField. The ModelRecord is responsible for
    constructing the ModelFields from the user data provided.

    Subclasses should provide a list of field types to use when the ModelRecord
    is constructed. Field types can either be ModelField subclasses, FromAttr,
    FromCallback, or None. If a field type is None, an empty field will be
    used.

    Example::

        class MyModelRecord(ModelRecord):
            field_types = [FromAttr("name"), FromAttr("age"), DOBField]

    Each column will be derived from the same user data object.  Each field
    just provides a view of the user data.
    """

    #: list of field types to use when constructing columns of data. If None,
    #  an empty field will be used.
    field_types: t.List[t.Union[t.Type[ModelField], FromAttr, FromCallback, None]]

    def __init__(self, user_data: t.Any):
        super(ModelRecord, self).__init__()
        self.user_data = user_data
        self.parent: t.Optional[ModelRecord] = None
        self.child_records: t.List[ModelRecord] = list()
        self.fields: t.List[ModelField] = self._to_fields()
        self.column_count: int = len(self.fields)
        self.record_key: uuid.UUID = uuid.uuid1()

    def append_record(self, child_record: "ModelRecord"):
        """Add a record to the end of the list of child records."""
        self.child_records.append(child_record)
        child_record.parent = self

    def insert_record(self, position: int, child_record: "ModelRecord"):
        """Insert a record at the given position in the list of child records."""
        self.child_records.insert(position, child_record)
        child_record.parent = self

    def remove_record(self, child_record: "ModelRecord"):
        """Remove the given record from the list of child records."""
        try:
            self.child_records.remove(child_record)
        except ValueError:
            self._remove_nonlocal_child(child_record)

    def _remove_nonlocal_child(self, child_record: "ModelRecord"):
        """Remove a child record based on its record_key.

        This will work even if the record's memory location does not match
        the one stored in self.child_records.  This is required to support
        drag-and-drop in models connected to this model collection.
        """
        for local_child in self.child_records:
            if local_child.record_key == child_record.record_key:
                self.child_records.remove(local_child)
                return

    def data(self, column_number: int, role: ModelRole) -> t.Any:
        """Get data for the field located at the given column_number and role."""
        return self.fields[column_number].data(role)

    def set_data(self, column_number: int, value: t.Any, role: ModelRole):
        """Set data for the field located at the given column_number and role."""
        return self.fields[column_number].set_data(value, role)

    def sort_children(
        self,
        column_number: int = 0,
        key: t.Optional[t.Callable] = None,
        reverse: bool = False,
    ):
        """Sort the list of child records in-place, using the given column."""
        if key is None:

            def sort_key(x):
                return x.fields[column_number].sort_by

        else:

            def sort_key(x):
                return key(x)

        self.child_records.sort(key=sort_key, reverse=reverse)

    def filter_children(
        self, column_number: int = 0, filter_func: t.Optional[t.Callable] = None
    ):
        """Remove children that do not pass the filter for the given column."""
        filter_func = filter_func or (lambda _: True)
        for child in list(self.child_records):
            filter_by = child.fields[column_number].filter_by
            if not filter_func(filter_by):
                self.child_records.remove(child)

    def copy(self):
        """Create a copy of the record, including all child records.

        This does not copy the user data.
        """
        new_record = self.__class__(self.user_data)
        for child in self.child_records:
            new_record.append_record(child.copy())
        return new_record

    def _to_fields(self):
        """Create ModelFields for the row."""
        fields = []
        for field_type in self.field_types:
            if field_type is None:
                field = ModelField(self.user_data, display="")
            elif isinstance(field_type, (FromAttr, FromCallback)):
                field = ModelField(self.user_data, display=field_type)
            else:
                field = field_type(self.user_data)
            fields.append(field)
        return fields

    def __hash__(self):
        return hash(self.record_key)

    def __eq__(self, other):
        try:
            return self.record_key == other.record_key
        except:
            return False

    def __ne__(self, other):
        try:
            return self.record_key != other.record_key
        except:
            return False

    def __repr__(self):
        field_displays = [field.display for field in self.fields]
        hex_id = hex(id(self))
        return "<{classname}({fields}) at {hex_id}>" "".format(
            classname=self.__class__.__name__, fields=field_displays, hex_id=hex_id
        )


class ModelCollection:
    """Collects and organizes ModelRecords into a hierarchy.

    Provides an interface for adding and removing records while tracking the
    geometry and hierarchy of the underlying data.

    This class can be used as-is, but it is intended to be subclassed with
    a custom implementation of "populate" for whatever data structure is
    being used.
    """

    def __init__(
        self,
        user_data: t.Any = None,
        default_record_type: t.Optional[t.Type[ModelRecord]] = None,
        combine_header_labels: bool = True,
    ):
        """
        Args:
            user_data (optional): The underlying data structure to populate
                this collection with.  This is only useful if your data is
                already nicely packed in a single object.
            default_record_type (optional): The default ModelRecord subclass
                to use when creating new records.  This is only useful every
                row of your data is the same type.
            combine_header_labels (optional): If True, the header labels will
                be combined into a single string.  For example, if the first
                column has items with a "name" header label and items with a
                "age" header label, the final label will be "name | age".
                Header labels can always be overridden in the view.
        """
        super(ModelCollection, self).__init__()

        self.user_data = user_data
        self.default_record_type = default_record_type
        self.combine_header_labels = combine_header_labels

        self.child_records = list()
        self.column_count = 0
        self._header_labels = list()
        self._default_header_labels = list()
        if user_data is not None:
            self.populate(user_data)

    def populate(self, user_data: t.Any):
        """Populate this collection with the given data.

        This method can be implemented by subclasses.
        """
        pass

    def populate_from_uniform_sequence(
        self,
        user_data_sequence: t.Sequence,
        record_type: t.Type[ModelRecord],
        parent=None,
    ):
        """Helper: Populate this collection from a uniformly-typed sequence.

        This assumes that every record in the sequence is the same type. Useful
        for populating a collection that resembles a homogeneous list.
        """
        record_type = record_type or self.default_record_type
        if record_type is None:
            raise TypeError("A ModelRecord subclass must be provided!")
        new_records = []
        for user_data in user_data_sequence:
            model_record = record_type(user_data)
            self.append_record(model_record, parent=parent)
            new_records.append(model_record)
        return new_records

    def populate_from_sequence(
        self,
        user_data_sequence: t.Sequence,
        record_type_map: t.Dict[t.Type, t.Type[ModelRecord]],
        parent: t.Optional[ModelRecord] = None,
    ):
        """Helper: Populate this collection from a sequence.

        This function allows different types of user data to be mapped to
        different types of ModelRecords.

        Args:
            user_data_sequence: A sequence of user data objects.
            record_type_map: A dictionary mapping user data types to ModelRecord
                classes.
            parent: The parent record to append the new records to. If None,
                the records will be appended to the root of the collection.
        """
        new_records = []
        for user_data in user_data_sequence:
            user_data_type = type(user_data)

            for mapped_type, record_type in record_type_map.items():
                if issubclass(user_data_type, mapped_type):
                    break
            else:
                raise TypeError(f"No record type found for user data: {user_data}")

            model_record = record_type(user_data)
            self.append_record(model_record, parent=parent)
            new_records.append(model_record)

        return new_records

    def append_user_data(
        self,
        user_data: t.Any,
        record_type: t.Optional[t.Type[ModelRecord]] = None,
        parent=None,
    ):
        """Append a new record to the collection, using the given user data."""
        record_type = record_type or self.default_record_type
        if record_type is None:
            raise TypeError("A ModelRecord subclass must be provided!")
        self.append_record(record_type(user_data), parent=parent)

    def append_record(
        self, record: ModelRecord, parent: t.Optional[ModelRecord] = None
    ):
        """Append ModelRecord to the records list for the given parent."""
        self._update_column_count(len(record.fields))

        if parent is None:
            self.child_records.append(record)
            record.parent = None
        else:
            parent.append_record(record)

        self._update_default_header_labels(record.fields)

    def insert_user_data(
        self,
        position: int,
        user_data: t.Any,
        record_type: t.Optional[t.Type[ModelRecord]] = None,
        parent=None,
    ):
        """Insert a new record at the given position, using the given user data."""
        record_type = record_type or self.default_record_type
        if record_type is None:
            raise TypeError("A ModelRecord subclass must be provided!")
        self.insert_record(position, record_type(user_data), parent=parent)

    def insert_record(
        self, position: int, record: ModelRecord, parent: t.Optional[ModelRecord] = None
    ):
        """Insert a child record at the given position.  If parent is None,
        insert the child to the top-level list for this collection"""
        if parent is None:
            self.child_records.insert(position, record)
            record.parent = None
        else:
            parent.insert_record(position, record)

        self._update_column_count(len(record.fields))

    def remove_record(self, record: ModelRecord):
        """Remove the given record and any descendants from the collection"""
        parent = record.parent
        if parent is None:
            self.child_records.remove(record)
        else:
            parent.remove_record(record)

    def remove_records(self, records: t.Sequence[ModelRecord]):
        """remove the given records and any of their descendants from the collection"""
        for record in records:
            self.remove_record(record)

    def reparent_record(
        self, child_record: ModelRecord, new_parent_record: ModelRecord
    ):
        """Reparent the child record under the new parent record"""
        old_parent_record = child_record.parent
        if old_parent_record is None:
            old_parent_record = self
        old_parent_record.remove_record(child_record)
        new_parent_record.append_record(child_record)

    def _update_column_count(self, new_count):
        """Update the column count for this collection, if necessary"""
        self.column_count = max((new_count, self.column_count))

    def _update_default_header_labels(self, fields):
        """Update the default labels for each column of the Collection.

        If the combine_header_labels boolean on this ModelCollection instance
        is True, any label collisions will be resolved with a pipe character:

        "label_one | label_two"

        If not, the first-assigned label will get precedence
        """

        header_labels = self._default_header_labels
        header_label_len = len(header_labels)
        for i in range(self.column_count):
            # If the field is populating a column that hasn't been used before
            # just use the label from the new field
            if i + 1 > header_label_len:
                header_labels.append(fields[i].header_label)
                continue

            try:
                label_for_column = header_labels[i]
                new_label = fields[i].header_label
            except IndexError:
                continue

            if new_label is None:
                continue

            # If the previously-set label was not provided, use the new label
            if label_for_column is None:
                header_labels[i] = new_label
                continue

            # If there is no collision, continue to the next column.
            # We're using endswith to account for any previously-combined labels
            if label_for_column.endswith(new_label):
                continue

            # either use the old label or a divided label, per the
            # combine_header_labels value
            elif self.combine_header_labels is True:
                existing_label = header_labels[i]
                header_labels[i] = "{label_one} | {label_two}".format(
                    label_one=existing_label, label_two=new_label
                )

    def refresh_column_count(self):
        """Return the max number of fields for all records in this collection"""
        self.column_count = max([len(record.fields) for record in self.all_records])

    def use_record_for_header_labels(self, record_type: t.Type[ModelRecord]):
        """Use the given record type's field header labels as the default"""
        # raise an exception if any of the field types are not ModelFields
        header_labels = []
        for field in record_type.field_types:
            if field is None:
                header_labels.append(None)
            else:
                header_labels.append(field.header_label)

    def sort_in_place(
        self, column_number: int = 0, key: t.Optional[t.Callable] = None, reverse=False
    ):
        """Sort the model collection by reordering all child records in-place"""
        for record in self.all_records:
            record.sort_children(column_number=column_number, key=None, reverse=reverse)

    def filter_in_place(
        self, column_number: int = 0, filter_func: t.Optional[t.Callable] = None
    ):
        """Filter the model collection by applying filter_function to the
        user data for every child record.  If the filter_function returns False,
        the record and any of its children are removed from the collection"""
        for record in self.all_records:
            record.filter_children(column_number=column_number, filter_func=filter_func)

    def find_record_with_user_data(self, user_data: t.Any):
        """Find the first record in this collection that uses the given user data"""
        for record in self.all_records:
            if record.user_data == user_data:
                return record

    def clear(self):
        """Remove all child records from the collection"""
        self.child_records = []
        self.column_count = 0

    @property
    def all_records(self) -> t.List[ModelRecord]:
        """A flat list of all records in this ModelCollection.

        This includes all descendant records as well.
        """
        records = list(self.child_records)
        for record in records:
            records.extend(record.child_records)
        return records

    @property
    def header_labels(self) -> t.List[t.Optional[str]]:
        """The list of header labels for this collection."""
        if self._header_labels:
            return self._header_labels
        return self._default_header_labels

    @header_labels.setter
    def header_labels(self, labels: t.List[t.Optional[str]]):
        self._header_labels = labels
