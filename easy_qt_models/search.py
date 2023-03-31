from typing import Callable, List, Optional, Union, Any, Sequence
from operator import eq

from easy_qt_models import EasySortFilterModel, EasyModel
from easy_qt_models.base_collection import ModelRecord

from PySide2 import QtCore

SearchFunc = Callable[[Any, Any], bool]
SortFunc = Callable[[Any, Any], bool]


__all__ = ["EasySearchModel"]


class EasySearchModel(EasySortFilterModel):
    """SortFilterModel with additional search-oriented functionality.

    This class takes a two-argument search_func in place of a one-argument
    filter_func, allowing easier use of dynamic searching features from
    Item Views.

    Additionally, we support complex hierarchical filtering by default, and
    caching of search results for improved performance.

    The search term for the model can be set with the `search_for` property.
    """

    def __init__(
        self,
        source_model: EasyModel,
        sortable: bool = True,
        search_parents: bool = True,
        search_children: bool = True,
        search_all_columns: bool = True,
        search_func: Optional[SearchFunc] = None,
        sort_func: Optional[SortFunc] = None,
        parent=None,
    ):
        """
        Args:
            source_model (EasyModel): The model to be filtered.

            sortable (bool): Whether the model is sortable.

            search_parents (bool): Whether to search the parents of a row
                when filtering.  If True, the filter will not remove any item
                if its parents are not also removed.

            search_children (bool): Whether to search the children of a row.
                If True, the filter will not remove any item if any of its
                children are not also removed.

            search_all_columns (bool): Whether to use each column's results
                when searching. If True, this is equivalent to using
                model.setFilterKeyColumn(-1)

            search_func (SearchFunc): The function to use when searching. The
                function's arguments should be the record and the search term.

            sort_func (SortFunc): The function to use when sorting.

            parent (QObject): The parent of this object.
        """
        super().__init__(
            source_model,
            sortable=sortable,
            filterable=True,
            sort_func=sort_func,
            parent=parent,
        )

        self.search_all_columns = search_all_columns
        self.search_parents = search_parents
        self.search_children = search_children
        self.search_func = search_func or eq

        self._search_for = None
        self._filter_cache = dict()

    def filterAcceptsRow(self, row_number: int, parent_index: QtCore.QModelIndex):
        """Reimplementation: Filter a row based on the search term.

        The search functionality is modulated by the `search_parents` and
        `search_children` attributes.  If `search_parents` is True, the
        filter will not remove any item if its parents are not also removed.
        If `search_children` is True, the filter will not remove any item if
        any of its children are not also removed.
        """

        column_number = self.filter_key_column

        record = self.get_record_to_filter(row_number, parent_index)
        accepted = self.record_passes_filter(record, column_number)
        if accepted or not self.search_parents:
            return accepted

        ancestors_accepted = self.ancestors_pass_filter(parent_index, column_number)
        if ancestors_accepted or not self.search_children:
            return ancestors_accepted

        index = self.source_model.index(row_number, column_number, parent_index)
        descendants_accepted = self.descendants_pass_filter(index, column_number)
        return descendants_accepted

    def ancestors_pass_filter(
        self, ancestor_index: QtCore.QModelIndex, column_number: int
    ) -> bool:
        """Returns True if any ancestor rows of the given index pass the filter."""
        record = ancestor_index.internalPointer()
        while record is not None:
            if self.record_passes_filter(record, column_number):
                return True
            ancestor_index = ancestor_index.parent()
            record = ancestor_index.internalPointer()
        return False

    def descendants_pass_filter(
        self, index: QtCore.QModelIndex, column_number: int
    ) -> bool:
        child_indexes = [
            self.source_model.index(row, column_number, index)
            for row in range(self.source_model.rowCount(index))
        ]

        # raise Exception("stop")
        for child_index in child_indexes:
            child_record = self.get_record_to_filter(
                child_index.row(), child_index.parent()
            )
            accepted = self.record_passes_filter(child_record, column_number)
            if accepted:
                return True
            descendants_accepted = self.descendants_pass_filter(
                child_index, column_number
            )
            if descendants_accepted:
                return True
        return False

    def record_passes_filter(self, record: ModelRecord, column_number: int) -> bool:
        """Given a Record object and a column number to search by, return True
        if this model's search_func accepts the record.  If column_number is -1,
        iteratively search each column's data and return True if any column is
        accepted.  The results of this function are cached for speed.  The cache
        is reset every time a new search term is set, but subclasses should be
        aware that they might need to flush the cache if data is changing
        outside of the search term"""

        # If the search function result has already been cached use it
        try:
            return self._filter_cache[record]
        except KeyError:
            pass

        # Apply the search_func to the item or items, and cache the result

        # A filter key column of -1 is a special value indicating that we intend
        # to search through the filterable data for every column.
        if column_number == -1:
            data = [
                record.data(i, self.filterRole()) for i in range(len(record.fields))
            ]
            accepted = any([self.search_func(self.search_for, d) for d in data])
        else:
            data = record.data(column_number, self.filterRole())
            accepted = self.search_func(self.search_for, data)
        self._filter_cache[record] = accepted

        return accepted

    @property
    def search_for(self):
        """The search term for filtering the model"""
        return self._search_for

    @search_for.setter
    def search_for(self, value: Any):
        """Set the search term for filtering the model"""
        self._filter_cache = dict()
        with self.layout_change_ctx():
            self._search_for = value

    def set_search_value(self, value: Any):
        """Helper function for easier connection from signals."""
        self.search_for = value

    def search_match(self, search_against: Any) -> bool:
        return self.search_func(self.search_for, search_against)

    def filterKeyColumn(self):
        if self.search_all_columns:
            return -1
        return super(EasySearchModel, self).filterKeyColumn()

    @property
    def filter_key_column(self) -> int:
        """Interface to model filterKeyColumn() method."""
        return self.filterKeyColumn()

    @filter_key_column.setter
    def filter_key_column(self, value: int):
        """Set the column to search by when filtering the model.

        -1 is a special value indicating that we intend to search through the
        filterable data for every column.

        You can also set the `search_all_columns` attribute to True to achieve
        the same effect.
        """
        self.setFilterKeyColumn(value)

    def flush_filter_cache(self):
        """Clear the cache of search results.

        Users may need to call this method if data updates occur that can
        affect the search results.

        The filter cache is automatically cleared when the search term is set
        with either the `search_for` attribute or `set_search_value` method.
        """
        self._filter_cache = dict()


# Additional search functions


def nonconsecutive_match(
    needles: Sequence, haystack: Sequence, anchored=False, empty_returns_true=True
):
    """Searches for each item in one sequence in another sequence.

    Args:

        needles: The sequence to search for

        haystack: The sequence to search in

        anchored: If True, the first item in needles must match the first item
            in haystack.

        empty_returns_true: If True, an empty needles sequence will always
            return True.

    This checks if each character of "needle" can be found in order (but not
    necessarily consecutively) in haystack.

    For example, "mm" can be found in "matchmove", but not "move2d"
    "m2" can be found in "move2d", but not "matchmove"

    >>> nonconsecutive_match("m2", "move2d")
    True

    >>> nonconsecutive_match("m2", "matchmove")
    False

    "Anchored" ensures the first letter matches
    >>> nonconsecutive_match("atch", "matchmove", anchored=False)
    True

    >>> nonconsecutive_match("atch", "matchmove", anchored=True)
    False

    """

    # Low-hanging fruit are checked first: equivalency and empty arguments
    if needles == haystack:
        return True

    if len(haystack) == 0 and needles:
        # "a" is not in ""
        return False

    elif len(needles) == 0 and haystack:
        # "" is in "blah"
        return empty_returns_true

    # Ensure the Sequence is a list so we can work with each element by index
    haystack = list(haystack)

    # Handle the anchored search next, if the anchor is not not found, exit early
    if anchored:
        if needles[0] != haystack[0]:
            return False
            # First letter matches, remove it for further matches
            needles = needles[1:]

    # Do the rest of the search
    index = 0
    while True:
        try:
            needle = needles[index]
        except IndexError:
            # We've found all the needles in the haystack
            return True
        try:
            needle_pos = haystack.index(needle)
        except ValueError:
            return False
        else:
            haystack = haystack[needle_pos:-1]
        index += 1


def nonconsecutive_str_match(
    needle_str: str,
    haystack_str: str,
    anchored=False,
    empty_returns_true=True,
    ignore_case=False,
):
    """A search function for working with strings.

    The nonconsecutive_match checks to see if the given string exists in the
    search string, even if the characters in the string are nonconsecutive.
    ("abc" matches "aabsomethingc")
    """
    if ignore_case:
        needle_str = needle_str.lower()
        haystack_str = haystack_str.lower()
    return nonconsecutive_match(
        needle_str,
        haystack_str,
        anchored=anchored,
        empty_returns_true=empty_returns_true,
    )
