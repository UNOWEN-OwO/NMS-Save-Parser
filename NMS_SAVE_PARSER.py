# require
# PyQt5, lz4

import json
import struct
from sys import argv, exit
from pathlib import Path
from datetime import datetime, timedelta
from pytimeparse.timeparse import timeparse
import time

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
SHOW_DATETIME = True

DATETIME_LIST = ['BirthTime',
                 'DbTimestamp',
                 'EndTimeUTC',
                 'LastAlertChangeTime',
                 'LastBrokenTimestamp',
                 'LastChangeTimestamp',
                 'LastCompletedTimestamp',
                 'LastDebtChangeTime',
                 'LastEggTime',
                 'LastJudgementTime',
                 'LastTrustDecreaseTime',
                 'LastTrustIncreaseTime',
                 'LastUpdateTimestamp',
                 'LastUpkeepDebtCheckTime',
                 'StartTimeUTC',
                 'TimeOfLastIncomeCollection',
                 'Timestamp',
                 'TSrec',
                 ]

DATETIME_LIST_LIST = ['LastBuildingUpgradesTimestamps']

TIMEDELTA_LIST = ['HazardTimeAlive',
                  'SunTimer',
                  'TimeAlive',
                  'TimeLastMiniStation',
                  'TimeLastSpaceBattle',
                  'TotalPlayTime',
                  ]


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
            if SHOW_DATETIME:
                if type(item.data[index.column()]) == datetime:
                    item.data[index.column()] = datetime.fromisoformat(editor.text())
                elif type(item.data[index.column()]) == timedelta:
                    item.data[index.column()] = timedelta(seconds=timeparse(editor.text()))
            else:
                item.data[index.column()] = type(item.data[index.column()])(editor.text())
            super(JsonDelegate, self).setModelData(editor, model, index)
            if index.column() == 0:
                item.parent().remap_node()
        except ValueError:
            self.notificator.setText('Invalid Value, expect ' + str(type(self.tree.currentItem().data[index.column()])))
        except TypeError:
            self.notificator.setText('Invalid Datetime format, expected YYYY-MM-DD hh-mm-ss')


class JsonNode(QtWidgets.QTreeWidgetItem):

    def __init__(self, data):
        self.is_list = False
        self.data = data
        self.dataEdit = [True, data[1] is not None]
        self.node = dict()
        super(JsonNode, self).__init__([str(d) for d in data if d is not None])

    def find(self, find_str):
        queue = []
        if find_str in '#'.join([str(i) for i in self.data]).lower():
            queue = [self]
        for i in range(self.childCount()):
            queue += self.child(i).find(find_str)
        return queue

    def addChild(self, child):
        super(JsonNode, self).addChild(child)
        self.node[child.data[0]] = child

    def set_value(self, value):
        self.data[1] = value
        self.setText(1, str(value))

    def remap_node(self):
        self.node = dict([(v.data[0], v) for v in self.node.values()])


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
        self.tree_widget.setHeaderLabels(['Key', 'Value'])
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
        if self.json_data:
            self.find_queue = []
            self.find_str = None
            self.tree_widget.takeTopLevelItem(0)
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
        find_button = QtWidgets.QPushButton('Find')
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
        else:
            self.find_box.setFocus()

    def find_next(self):
        if self.find_box.text() != self.find_str:
            self.find()
        elif self.find_queue:
            self.find_idx = (self.find_idx + 1 + len(self.find_queue)) % len(self.find_queue)
            self.find_result()
        else:
            self.notification.setText('No result found')

    def find_prev(self):
        if self.find_box.text() != self.find_str:
            self.find()
        elif self.find_queue:
            self.find_idx = (self.find_idx - 1 + len(self.find_queue)) % len(self.find_queue)
            self.find_result()
        else:
            self.notification.setText('No result found')

    def find_result(self):
        if self.find_queue:
            self.notification.setText('{} of {} find'.format(self.find_idx+1, len(self.find_queue)))
            self.tree_widget.setCurrentItem(self.find_queue[self.find_idx])
            # self.tree_widget.scroll(0, 20)
        else:
            self.notification.setText('No result found')

    def recurse_json(self, data, key='Root', ts_list=False):
        if isinstance(data, dict):
            node = JsonNode([key, None])
            for key, val in data.items():
                row_item = self.recurse_json(val, key)
                row_item.setFlags(row_item.flags() | QtCore.Qt.ItemIsEditable)
                node.addChild(row_item)
        elif isinstance(data, list):
            node = JsonNode([key, None])
            node.is_list = True
            ts_list = key in DATETIME_LIST_LIST
            for i, val in enumerate(data):
                key = str(i)
                row_item = self.recurse_json(val, key, ts_list)
                row_item.setFlags(row_item.flags() | QtCore.Qt.ItemIsEditable)
                row_item.dataEdit[0] = False
                node.addChild(row_item)
        else:
            if SHOW_DATETIME:
                if ts_list or str(key) in DATETIME_LIST:
                    data = datetime.fromtimestamp(data)
                elif str(key) in TIMEDELTA_LIST:
                    data = timedelta(seconds=data)
            node = JsonNode([key, data])
        return node

    def exd_complete(self):
        try:
            if (sd := self.root_item.node['PlayerStateData'].node['SeasonData']).node['SeasonId'].data[1] != 0:
                expd_ms = [ms.node['Amount'].data[1] for stg in sd.node['Stages'].node.values() for ms in stg.node['Milestones'].node.values()]
                ms_v = self.root_item.node['PlayerStateData'].node['SeasonState'].node['MilestoneValues']
                self.tree_widget.setCurrentItem(ms_v)
                expd_ms_store = ms_v.node.values()
                if len(expd_ms) == len(expd_ms_store):
                    for s, d in zip(expd_ms, expd_ms_store):
                        d.set_value(s)
                    self.notification.setText('Done')
                else:
                    self.notification.setText('Milestone count error')
            else:
                self.notification.setText('Not a NMS Expedition save')
        except KeyError:
            self.notification.setText('Unable to resolve data')
        except Exception as e:
            print(':angri:', e)

    def switch_judgement(self, judge):
        if not self.tree_widget.currentItem() or self.tree_widget.currentItem().data[0] != 'SettlementJudgementType':
            self.find_box.setText('SettlementJudgementType')
            self.find()
        else:
            self.notification.setText(self.tree_widget.currentItem().data[1] + ' -> ' + judge)
            self.tree_widget.currentItem().setText(1, judge)
            self.tree_widget.currentItem().data[1] = judge


class JsonViewer(QtWidgets.QMainWindow):

    def __init__(self):
        super(JsonViewer, self).__init__()

        self.json_view = JsonView()

        self.setCentralWidget(self.json_view)
        self.setWindowTitle('NMS Save Parser')

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

        self.exp = self.menu.addMenu('Experimental')
        self.exp.addAction(self._set_action('&Complete Expedition Mission\n(Save then claim in game)', self.json_view.exd_complete))
        settlement_fix = self.exp.addMenu('Settlement Judgement\n(Jump next if not selecting any)')
        settlement_fix.addAction(self._set_action('&BuildingChoice', lambda: self.json_view.switch_judgement('BuildingChoice')))
        settlement_fix.addAction(self._set_action('&Policy', lambda: self.json_view.switch_judgement('Policy')))
        settlement_fix.addAction(self._set_action('&Request', lambda: self.json_view.switch_judgement('Request')))
        settlement_fix.addAction(self._set_action('&StrangerVisit', lambda: self.json_view.switch_judgement('StrangerVisit')))
        settlement_fix.addAction(self._set_action('&Conflict', lambda: self.json_view.switch_judgement('Conflict')))
        self.exp.addMenu(settlement_fix)
        self.exp.setDisabled(True)
        # exp.addAction('Combine Discovery')
        # exp.addAction('Combine Base')
        # exp.addAction('Export Base')
        # exp.addAction('Sort Slot')

        self.path = None
        if len(argv) > 1:
            self.open_file(argv[1])

        self.show()
        self.resize(800, 600)

    def _set_action(self, name, connect, **kwargs):
        act = QtWidgets.QAction(name, self)
        for k, v in kwargs.items():
            getattr(act, f'set{k}')(v)
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
            self.exp.setDisabled(False)

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
    global PATH, SAVE_MODE, SLICE, SHOW_DATETIME
    try:
        with open('config.json') as config:
            c = json.load(config)
            PATH = c['PATH']
            SAVE_MODE = c['SAVE_MODE']
            SLICE = c['SLICE']
            SHOW_DATETIME = c['SHOW_DATETIME']
    except KeyError:
        save_config()
    except OSError:
        save_config()
    except Exception as e:
        print(':angri:', e)


def save_config():
    with open('config.json', 'w') as config:
        json.dump({'PATH': PATH, 'SAVE_MODE': SAVE_MODE, 'SLICE': SLICE, 'SHOW_DATETIME': SHOW_DATETIME}, config)


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
        if SHOW_DATETIME:
            if type(node.data[1]) == datetime:
                return int(time.mktime(node.data[1].timetuple()))
                # return int(node.data[1].timestamp()) # Unable to use due to python bug :angri:
            elif type(node.data[1]) == timedelta:
                return int(node.data[1].total_seconds())
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

if '__main__' == __name__:
    main()
