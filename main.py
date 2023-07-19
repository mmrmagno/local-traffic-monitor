import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget
from PyQt5.QtCore import QTimer
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import psutil
import time

start_bytes_sent, start_bytes_recv = psutil.net_io_counters()[:2]
start_time = time.time()

process_traffic_data = {}

class AppCanvas(FigureCanvas):
    def __init__(self, parent=None):
        fig = Figure()
        self.axes = fig.add_subplot(111)
        super(AppCanvas, self).__init__(fig)
        self.setParent(parent)

    def plot(self, times, sent, received, label):
        self.axes.clear()
        self.axes.plot(times, sent, label='Bytes Sent')
        self.axes.plot(times, received, label='Bytes Received')
        self.axes.legend()
        self.axes.set_title(label)
        self.draw()

class NetworkTab(QWidget):
    def __init__(self):
        super().__init__()
        self.canvas = AppCanvas(self)
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        self.times = []
        self.sent = []
        self.received = []

    def update_plot(self, current_time, current_sent, current_received):
        self.times.append(current_time)
        self.sent.append(current_sent)
        self.received.append(current_received)

        self.canvas.plot(self.times, self.sent, self.received, "Overall Network Traffic")

class ProcessTab(QWidget):
    def __init__(self):
        super().__init__()
        self.process_tabs = []
        layout = QVBoxLayout()
        self.setLayout(layout)

    def update_process_tabs(self, process_names):
        global process_traffic_data

        layout = self.layout()
        while layout.count():
            layout_item = layout.takeAt(0)
            widget = layout_item.widget()
            if widget:
                widget.deleteLater()

        for process_name in process_names:
            if process_name in process_traffic_data:
                process_data = process_traffic_data[process_name]
                process_graph = ProcessGraphWidget(process_name)
                layout.addWidget(process_graph)
                process_graph.update_plot(process_data['times'], process_data['sent'], process_data['received'])

class ProcessGraphWidget(QWidget):
    def __init__(self, process_name):
        super().__init__()
        self.process_name = process_name
        self.canvas = AppCanvas(self)
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)

    def update_plot(self, times, sent, received):
        self.canvas.plot(times, sent, received, self.process_name)

class ApplicationWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.tab_widget = QTabWidget()

        self.network_tab = NetworkTab()
        self.process_tab = ProcessTab()

        self.tab_widget.addTab(self.network_tab, "Network Traffic")
        self.tab_widget.addTab(self.process_tab, "Running Processes")

        self.setCentralWidget(self.tab_widget)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_tabs)
        self.timer.start(1000)  # update every second

    def update_tabs(self):
        global start_bytes_sent, start_bytes_recv, start_time, process_traffic_data

        # Update NetworkTab
        current_bytes_sent, current_bytes_recv = psutil.net_io_counters()[:2]
        current_time = time.time() - start_time
        self.network_tab.update_plot(current_time, current_bytes_sent - start_bytes_sent, current_bytes_recv - start_bytes_recv)
        start_bytes_sent, start_bytes_recv = current_bytes_sent, current_bytes_recv

        # Update ProcessTab
        processes = psutil.process_iter(['name'])
        process_traffic_data.clear()
        for proc in processes:
            process_name = proc.info['name']
            if process_name not in process_traffic_data:
                process_traffic_data[process_name] = {'times': [], 'sent': [], 'received': []}

            current_bytes_sent, current_bytes_recv = proc.io_counters()[:2]
            process_traffic_data[process_name]['times'].append(current_time)
            process_traffic_data[process_name]['sent'].append(current_bytes_sent)
            process_traffic_data[process_name]['received'].append(current_bytes_recv)

        sorted_processes = sorted(process_traffic_data.keys(), key=lambda x: sum(process_traffic_data[x]['sent']), reverse=True)
        self.process_tab.update_process_tabs(sorted_processes[:4])

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = ApplicationWindow()
    w.show()
    sys.exit(app.exec_())
