from easy_qt_models.base_collection import (
    ModelField,
    ModelRecord,
    ModelCollection,
    FromAttr,
)
from easy_qt_models.base_model import EasyModel
from easy_qt_models.proxies import EasySortFilterModel
from easy_qt_models.search import EasySearchModel

from PySide2 import QtWidgets


class Animal:
    """Example business data class."""

    def __init__(self, name, sound):
        self.name = name
        self.sound = sound


class AnimalCategory:
    """Business data class with a collection"""

    def __init__(self, animal_type, animals):
        self.animal_type = animal_type
        self.animals = animals


class AnimalTypeField(ModelField):
    header_label = "Category"
    drag_enabled = True
    drop_enabled = True
    selectable = True
    display = FromAttr("animal_type")


class AnimalTypeRecord(ModelRecord):
    field_types = [AnimalTypeField, None]


class NameField(ModelField):
    drag_enabled = True
    header_label = "Name"
    display = FromAttr("name")


class SoundField(ModelField):
    drag_enabled = True
    header_label = "Sound"
    display = FromAttr("sound")


class AnimalRecord(ModelRecord):
    field_types = [NameField, SoundField]


class AnimalCollection(ModelCollection):
    def populate(self, animals):
        self.populate_from_uniform_sequence(animals, AnimalRecord)

    def add_animal(self, animal):
        new_row = AnimalRecord(animal)
        self.append_record(new_row)


class NestedAnimalCollection(ModelCollection):
    def populate(self, animal_types):
        self.populate_from_uniform_sequence(animal_types, AnimalTypeRecord)
        for animal_type in self.child_records:
            self.populate_from_uniform_sequence(
                animal_type.user_data.animals, AnimalRecord, parent=animal_type
            )


def print_animal(index):
    record = index.internalPointer()
    field = record.fields[index.column()]


def example_sequence_model():
    """return a flat model populated with some animals and their noises"""
    # business data
    animals = (
        Animal("dog", "bark"),
        Animal("cat", "meow"),
        Animal("crow", "caw"),
        Animal("duck", "quack"),
        Animal("cow", "moo"),
        Animal("pig", "oink"),
        Animal("robot", "beep"),
    )

    # model collection
    collection = AnimalCollection(animals)
    # collection.use_record_header_labels(AnimalRecord)

    # Qt model
    model = EasyModel(collection)

    return model


def example_nested_model():
    # business data
    domestics = (Animal("dog", "bark"), Animal("cat", "meow"))
    domestic_type = AnimalCategory("domestic", domestics)
    birds = (Animal("crow", "caw"), Animal("duck", "quack"))
    bird_type = AnimalCategory("bird", birds)
    farms = (Animal("cow", "moo"), Animal("pig", "oink"))
    farm_type = AnimalCategory("farm", farms)
    imposters = (Animal("robot", "beep"),)
    imposter_type = AnimalCategory("imposter", imposters)

    # model collection
    collection = NestedAnimalCollection(
        [domestic_type, bird_type, farm_type, imposter_type]
    )

    # model
    model = EasyModel(collection)

    view = example_get_view(model)
    view.show()

    return view


def example_get_view(model):
    """given a Qt model, make a tree view, plug in the model and return it"""
    view = QtWidgets.QTreeView()
    view.setModel(model)
    view.clicked.connect(print_animal)
    return view


def example_get_proxy_view(model):
    """given a Qt model, make a tree view, plug in the model and return it"""
    view = QtWidgets.QTreeView()
    view.setModel(model)

    def print_animal_proxy(proxy_index):
        source_idx = model.mapToSource(proxy_index)
        print_animal(source_idx)

    view.clicked.connect(print_animal_proxy)
    return view


def example_base_model():
    """return a view populated by a simple base model"""
    model = example_sequence_model()
    view = example_get_view(model)
    view.show()
    return view


def example_drag_drop_model():
    """return a view populated by a simple base model"""
    view = example_nested_model()
    # view.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
    view.setDragEnabled(True)
    view.setAcceptDrops(True)
    view.setDropIndicatorShown(True)
    view.show()
    return view


def example_filter_func(filter_data):
    """a function suitable for passing into a SortFilterModel as a filter_func"""
    if filter_data.lower().startswith("c"):
        return True
    return False


def example_filter_model():
    """return a view populated by a SortFilterModel that only shows animals
    whose names start with the letter c"""
    model = example_sequence_model()
    proxy_model = EasySortFilterModel(model, filter_func=example_filter_func)
    view = example_get_proxy_view(proxy_model)
    view.show()
    return view


def example_sort_model():
    """return a view populated by a SortFilterModel that can be sorted in the UI
    by clicking the header sections"""
    model = example_sequence_model()
    proxy_model = EasySortFilterModel(model)
    view = example_get_proxy_view(proxy_model)
    view.setSortingEnabled(True)
    view.show()
    return view


def example_search_model():
    """return a dialog with a search field and a view populated with a
    SortSearchStringModel"""
    dialog = ExampleSearch()
    dialog.show()
    return dialog


class ExampleSearch(QtWidgets.QDialog):
    """A simple dialog with a search field and a tree-view"""

    def __init__(self):
        super(ExampleSearch, self).__init__()

        model = example_sequence_model()

        def search(a, b):
            return a in b

        search_proxy = EasySearchModel(model, search_func=search)
        search_proxy.search_for = ""
        search_proxy.search_all_columns = False

        # widgets
        search_field = QtWidgets.QLineEdit()
        item_view = example_get_proxy_view(search_proxy)

        # layouts
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        # populate
        layout.addWidget(search_field)
        layout.addWidget(item_view)

        # signals / slots
        search_field.textChanged.connect(search_proxy.set_search_value)


# keep Qt objects from being garbage-collected
ui_register = dict()


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    ui_register["base"] = example_base_model()
    ui_register["filter"] = example_filter_model()
    ui_register["sort"] = example_sort_model()
    ui_register["search"] = example_search_model()
    ui_register["nested"] = example_nested_model()
    # NOTE: drag and drop is still *potentially slightly* broken.
    ui_register["dnd"] = example_drag_drop_model()
    app.exec_()
