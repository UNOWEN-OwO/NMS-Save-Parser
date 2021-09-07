# require
# PyQt5, lz4

import json
import struct
from sys import argv, exit
from pathlib import Path

import lz4.block as lb
from PyQt5 import QtCore
from PyQt5 import QtWidgets

NMS_FILE_TYPE = ['As Source (*.hg)',
                 'Decompressed NMS Save (*.hg)',
                 'Compressed NMS Save (*.hg)',
                 'Mapped NMS Save (*.hg)',
                 'All Files (*)',
                 ]
PATH = '.\\'
SAVE_MODE = 0
SRC_MODE = 1
SLICE = 524288

SIGNAL = False


class JsonDelegate(QtWidgets.QItemDelegate):

    def __init__(self, parent, notificator):
        super(JsonDelegate, self).__init__(parent)
        self.tree = parent
        self.notificator = notificator

    def createEditor(self, parent, option, index):
        if self.tree.currentItem().dataEdit[index.column()]:
            return super(JsonDelegate, self).createEditor(parent, option, index)

    def setModelData(self, editor, model, index):
        try:
            item = self.tree.currentItem()
            item.data[index.column()] = type(item.data[index.column()])(editor.text())
            super(JsonDelegate, self).setModelData(editor, model, index)
        except ValueError:
            self.notificator.setText('Invalid Value, expect ' + str(type(self.tree.currentItem().data[index.column()])))


class JsonNode(QtWidgets.QTreeWidgetItem):
    is_list = False

    def __init__(self, data):
        super(JsonNode, self).__init__([str(d) for d in data if d is not None])
        self.data = data
        self.dataEdit = [True, data[1] is not None]

    def find(self, find_str):
        queue = []
        if find_str in '#'.join([str(i) for i in self.data]).lower():
            queue = [self]
        for i in range(self.childCount()):
            queue += self.child(i).find(find_str)
        return queue


class JsonView(QtWidgets.QWidget):
    def __init__(self):
        super(JsonView, self).__init__()

        self.find_box = None
        self.tree_widget = None
        self.json_data = None
        self.find_str = None
        self.find_queue = []
        self.find_idx = 0

        # Find UI
        find_layout = self.find_toolbar()

        # Tree
        self.tree_widget = QtWidgets.QTreeWidget()
        self.tree_widget.setHeaderLabels(["Key", "Value"])
        self.tree_widget.header().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)

        self.root_item = self.recurse_json(None)
        self.tree_widget.addTopLevelItem(self.root_item)

        # Add table to layout
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.tree_widget)

        # Group box
        self.gbox = QtWidgets.QGroupBox()
        self.gbox.setLayout(layout)

        # Notification
        self.notification = QtWidgets.QLabel()
        self.notification.setText('Ready')

        layout2 = QtWidgets.QVBoxLayout()
        layout2.addLayout(find_layout)
        layout2.addWidget(self.gbox)
        layout2.addWidget(self.notification)

        self.setLayout(layout2)

    def open_file(self, path):
        self.notification.setText('Loading...')
        self.notification.repaint()
        self.json_data = load_file(path)
        self.reset()
        self.gbox.setTitle(Path(path).name)

    def save_file(self, path, mode):
        if mode == 0:
            mode = SRC_MODE
        self.notification.setText('Saving...')
        self.notification.repaint()
        data = serialize_json(self.root_item)
        if mode < 3:
            map_keys(data, encode_map)

        if mode != 2:
            with open(path, 'wb') as file:
                file.write(json.dumps(data, separators=(',', ':'), ensure_ascii=False).encode('utf-8'))
                if mode == 1:
                    file.write(b'\x00')

        if mode == 2:
            with open(path, 'wb') as file:
                file.write(compress_file(json.dumps(data, separators=(',', ':'), ensure_ascii=False).encode('utf-8')))

        self.notification.setText('Ready')

    def reset(self):
        self.notification.setText('Loading...')
        self.notification.repaint()
        self.tree_widget.takeTopLevelItem(0)
        if self.json_data:
            self.root_item = self.recurse_json(self.json_data)
        self.tree_widget.addTopLevelItem(self.root_item)
        self.tree_widget.setItemDelegate(JsonDelegate(self.tree_widget, self.notification))
        self.notification.setText('Ready')
        self.notification.repaint()

    def export_node(self):
        if item := self.tree_widget.currentItem():
            global PATH
            path, f = QtWidgets.QFileDialog.getSaveFileName(self, 'Save node', PATH + '\\' + ((item.parent().data[0]+'_'+item.data[0]) if item.parent() and item.parent().is_list else item.data[0]), 'Format json (*.json);;Minify json (*.json);;All Files (*)')
            if path:
                PATH = str(Path(path).parent)
                save_config()
                with open(path, 'wb') as file:
                    file.write(json.dumps(serialize_json(item) if item.data[1] is None else {item.data[0]: item.data[1]}, separators=(',', ':') if f == 'Minify json (*.json)' else None, ensure_ascii=False).encode('utf-8'))

    def find_toolbar(self):
        # Text box
        self.find_box = QtWidgets.QLineEdit()
        self.find_box.returnPressed.connect(self.find)

        # Find Button
        find_button = QtWidgets.QPushButton("Find")
        find_button.clicked.connect(self.find)

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.find_box)
        layout.addWidget(find_button)
        return layout

    def find(self):
        find_str = self.find_box.text()

        if find_str:
            if find_str != self.find_str:
                self.find_str = find_str
                self.find_idx = -1
                self.find_queue = self.root_item.find(self.find_str.lower())

            self.find_next()

    def find_next(self):
        if self.find_box.text() != self.find_str:
            find()
        elif self.find_queue:
            self.find_idx = (self.find_idx + 1 + len(self.find_queue)) % len(self.find_queue)
            self.find_result()

    def find_prev(self):
        if self.find_box.text() != self.find_str:
            find()
        elif self.find_queue:
            self.find_idx = (self.find_idx - 1 + len(self.find_queue)) % len(self.find_queue)
            self.find_result()

    def find_result(self):
        if self.find_queue:
            self.notification.setText('{} of {} find'.format(self.find_idx+1, len(self.find_queue)))
            self.tree_widget.setCurrentItem(self.find_queue[self.find_idx])
        else:
            self.notification.setText('No result found')

    def recurse_json(self, data, key='Root'):
        if SIGNAL:
            return None
        if isinstance(data, dict):
            node = JsonNode([key, None])
            for key, val in data.items():
                row_item = self.recurse_json(val, key)
                row_item.setFlags(row_item.flags() | QtCore.Qt.ItemIsEditable)
                node.addChild(row_item)
        elif isinstance(data, list):
            node = JsonNode([key, None])
            node.is_list = True
            for i, val in enumerate(data):
                key = str(i)
                row_item = self.recurse_json(val, key)
                row_item.setFlags(row_item.flags() | QtCore.Qt.ItemIsEditable)
                row_item.dataEdit[0] = False
                node.addChild(row_item)
        else:
            node = JsonNode([key, data])
        return node


class JsonViewer(QtWidgets.QMainWindow):

    def __init__(self):
        super(JsonViewer, self).__init__()

        self.json_view = JsonView()

        self.setCentralWidget(self.json_view)
        self.setWindowTitle("NMS Save Tools")

        self.menu = self.menuBar()
        self.file = self.menu.addMenu('File')

        self.file.addAction(self._set_action('&Open', self.open_file, Shortcut='Ctrl+O'))
        self.file.addAction(self._set_action('&Save', self.save_file, Shortcut='Ctrl+S', Disabled=True))
        self.file.addAction(self._set_action('&Save As', self.save_file_as, Shortcut='Ctrl+Shift+S', Disabled=True))
        self.file.addAction(self._set_action('&Reset', self.json_view.reset, Shortcut='Ctrl+R', Disabled=True))
        self.file.addAction(self._set_action('&Reload', self.reload_file, Shortcut='Ctrl+L', Disabled=True))
        self.file.addAction(self._set_action('&Exit', QtWidgets.qApp.quit, Shortcut='Alt+F4'))

        self.edit = self.menu.addMenu('Edit')
        self.edit.addAction(self._set_action('&Find', self.json_view.find, Shortcut='Ctrl+F'))
        self.edit.addAction(self._set_action('&Find Next', self.json_view.find_next, Shortcut='F3'))
        self.edit.addAction(self._set_action('&Find Prev', self.json_view.find_prev, Shortcut='Shift+F3'))

        self.tool = self.menu.addMenu('Convert')
        self.tool.addAction(self._set_action('&As Source', lambda: self.set_convert(0), Checkable=True, Checked=False))
        self.tool.addAction(self._set_action('&Decompressed', lambda: self.set_convert(2), Checkable=True, Checked=False))
        self.tool.addAction(self._set_action('&Compressed', lambda: self.set_convert(1), Checkable=True, Checked=False))
        self.tool.addAction(self._set_action('&Mapped', lambda: self.set_convert(3), Checkable=True, Checked=False))
        self.tool.setDisabled(True)

        self.export = self.menu.addMenu('Export')
        self.export.addAction(self._set_action('&Export Node', self.json_view.export_node, Shortcut='Ctrl+E'))
        self.export.setDisabled(True)

        # exp = self.menu.addMenu('Experimental')
        # exp.addAction('Combine Discovery')
        # exp.addAction('Combine Base')
        # exp.addAction('Export Base')
        # exp.addAction('Sort Slot')

        self.path = None
        if len(argv) > 1:
            self.open_file(argv[1])

        self.show()

    def _set_action(self, name, connect, **kwargs):
        act = QtWidgets.QAction(name, self)
        for k, v in kwargs.items():
            getattr(act, f"set{k}")(v)
        act.triggered.connect(connect)
        return act

    def set_convert(self, mode=0):
        global SAVE_MODE
        SAVE_MODE = mode
        save_config()
        for idx in range(self.tool.columnCount()):
            if idx == mode:
                self.tool.actions()[idx].setChecked(True)
            else:
                self.tool.actions()[idx].setChecked(False)

    def open_file(self, path=None):
        global PATH
        self.path = path or QtWidgets.QFileDialog.getOpenFileName(self, 'Open file', PATH, 'NMS Save (*.hg);;All Files (*)')[0]
        if self.path:
            PATH = str(Path(self.path).parent)
            save_config()
            self.json_view.open_file(self.path)
            for action in self.file.actions():
                action.setDisabled(False)
            self.tool.setDisabled(False)
            self.tool.actions()[SAVE_MODE].setChecked(True)
            self.export.setDisabled(False)

    def reload_file(self):
        self.json_view.open_file(self.path)

    def save_file(self):
        self.json_view.save_file(self.path, SRC_MODE)

    def save_file_as(self):
        global PATH
        path, f = QtWidgets.QFileDialog.getSaveFileName(self, 'Save file', PATH, ';;'.join(sorted(NMS_FILE_TYPE, key=lambda x: NMS_FILE_TYPE.index(x) != SAVE_MODE)))
        if path:
            PATH = str(Path(self.path).parent)
            save_config()
            self.json_view.save_file(path, NMS_FILE_TYPE.index(f))

    # def keyPressEvent(self, e):
    #     if e.key() == QtCore.Qt.Key_Escape:
    #         self.close()


def load_config():
    global PATH, SAVE_MODE, SLICE
    try:
        with open('config.json') as config:
            c = json.load(config)
            PATH = c['PATH']
            SAVE_MODE = c['SAVE_MODE']
            SLICE = c['SLICE']
    except KeyError:
        save_config()
    except OSError:
        save_config()
    except Exception as e:
        print(':angri:', e)


def save_config():
    with open('config.json', 'w') as config:
        json.dump({'PATH': PATH, 'SAVE_MODE': SAVE_MODE, 'SLICE': SLICE}, config)


def map_keys(node, mapping):
    if isinstance(node, dict):
        for k in list(node.keys()):
            if k in mapping:
                node[mapping[k]] = node.pop(k)
            else:
                print('Key mapping not found: ', k)
        for k in node.keys():
            map_keys(node[k], mapping)
    elif isinstance(node, list):
        for k in node:
            map_keys(k, mapping)


def serialize_json(node):
    if node.data[1] is not None:
        return node.data[1]
    elif node.is_list:
        return [serialize_json(node.child(i)) for i in range(node.childCount())]
    else:
        data = dict()
        for i in range(node.childCount()):
            data[node.child(i).data[0]] = serialize_json(node.child(i))
        return data


def compress_file(data):
    ret = b''
    while block := data[:SLICE]:
        data = data[SLICE:]
        block += b'\x00' if len(block) < SLICE and block[-1] != b'\x00' else b''
        c = lb.compress(block, store_size=False)
        ret += b'\xE5\xA1\xED\xFE' + struct.pack('i', len(c)) + struct.pack('i', len(block)) + b'\x00' * 4 + c
    return ret


# return mapped json object
def load_file(file_path):
    global SRC_MODE
    with open(file_path, 'rb') as src:
        dest = b''
        while src.read(4) == b'\xE5\xA1\xED\xFE':
            block_size = struct.unpack('i', src.read(4))[0]
            dest_size = struct.unpack('i', src.read(4))[0]
            src.read(4)
            dest += lb.decompress(src.read(block_size), uncompressed_size=dest_size)
            # print('block_size:', block_size, 'dest_size:', dest_size, 'actual_size:', len(dest))

        if src.read(1):
            src.seek(0)
            dest = src.read().rstrip(b'\x00')
            SRC_MODE = 3
        else:
            dest = dest.rstrip(b'\x00')
            SRC_MODE = 2
        data = json.loads(dest.decode('utf-8'))
        if len([k for k in data.keys() if len(k) == 3]) > 3:
            map_keys(data, decode_map)
            if SRC_MODE == 3:
                SRC_MODE = 1
        return data


def main():
    load_config()
    qt_app = QtWidgets.QApplication([])
    json_viewer = JsonViewer()
    exit(qt_app.exec_())


# require mapping.json, you can get latest mapping from https://github.com/monkeyman192/MBINCompiler/releases
encode_map = dict()
decode_map = dict()
with open('mapping.json', encoding='utf-8') as mapping_file:
    km = json.load(mapping_file)
    print('libMBIN_version:', km['libMBIN_version'])
    for m in km['Mapping']:
        decode_map[m['Key']] = m['Value']
        encode_map[m['Value']] = m['Key']

if "__main__" == __name__:
    main()
