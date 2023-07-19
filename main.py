import sys
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget, QLabel, QTextEdit, \
    QMessageBox, QPushButton
from PyQt5.QtCore import QTimer, pyqtSignal
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import psutil
import time

from PyQt5 import QtWidgets, QtCore


start_time = time.time()
process_traffic_data = {}
recording_enabled = False
recording_file = None


class AppCanvas(FigureCanvas):
    def __init__(self, parent=None, width=10, height=4, dpi=100, title=''):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        self.title = title  # Added this line here

        super(AppCanvas, self).__init__(fig)
        self.setParent(parent)

        FigureCanvas.setSizePolicy(self, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

    def plot(self, times, sent, received):
        print(f"Plotting data:\nTimes: {times}\nSent: {sent}\nReceived: {received}")  # Debug line
        self.axes.clear()
        if times:  # Plot data only if times array is not empty
            self.axes.plot(times, sent, label='Bytes Sent')
            self.axes.plot(times, received, label='Bytes Received')
            self.axes.set_ylim(bottom=0)  # Ensure y-axis starts from 0
            self.axes.legend()

            self.axes.set_xlabel('Time (s)')
            self.axes.set_ylabel('Data Transferred (Bytes)')
            self.axes.set_title(self.title)

        self.draw()


class NetworkTab(QWidget):
    def __init__(self):
        super().__init__()
        self.canvas = AppCanvas(self, title="Overall Tracking")
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

        self.canvas.plot(self.times, self.sent, self.received)
        if recording_enabled:
            self.write_to_recording_file(current_time, current_sent, current_received)

    def write_to_recording_file(self, current_time, current_sent, current_received):
        global recording_file
        with open(recording_file, 'a') as file:
            file.write(f"{time.ctime(current_time)}\n")
            file.write(f"Bytes Sent: {current_sent}\n")
            file.write(f"Bytes Received: {current_received}\n\n")


class ProcessTab(QWidget):
    process_clicked = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        self.process_label = QLabel("Running Processes")
        self.process_text = QTextEdit()

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.update_process_list)

        self.process_graphs = [AppCanvas(self, title="Process Graph") for _ in range(4)]

        layout = QVBoxLayout()
        layout.addWidget(self.process_label)
        layout.addWidget(self.process_text)
        layout.addWidget(self.refresh_button)

        for graph in self.process_graphs:
            layout.addWidget(graph)

        self.setLayout(layout)

        self.process_text.setReadOnly(True)
        self.process_text.setLineWrapMode(QTextEdit.NoWrap)

        self.process_text.cursorPositionChanged.connect(self.process_click_handler)

    def update_process_list(self):
        processes = [proc.info['name'] for proc in psutil.process_iter(['name'])]

        self.process_text.clear()
        self.process_text.append('\n'.join(processes))

    def update_process_traffic_data(self):
        global process_traffic_data
        process_traffic_data.clear()
        process_list = self.process_text.toPlainText().split('\n')
        for process_name in process_list:
            process_traffic_data[process_name] = {'times': [], 'sent': [], 'received': []}

    def process_click_handler(self):
        selected_text = self.process_text.textCursor().selectedText()
        if selected_text:
            process_name = str(selected_text)
            self.process_clicked.emit(process_name)

    def update_process_tabs(self, sorted_processes):
        """
        Update the process tabs with traffic information of the most active processes.
        sorted_processes : list
            List of most active processes, each process is represented as a tuple
            (process_name, traffic_data), where traffic_data is a dict with keys
            'times', 'sent', 'received', representing the time stamps, bytes sent,
            and bytes received of the process.
        """
        for i, (process_name, traffic_data) in enumerate(sorted_processes):
            times = traffic_data['times']
            sent = traffic_data['sent']
            received = traffic_data['received']

            self.process_graphs[i].axes.set_title(process_name)  # Set graph title as process name
            self.process_graphs[i].plot(times, sent, received)


class ApplicationWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.tab_widget = QTabWidget()
        self.start_bytes_sent, self.start_bytes_recv = psutil.net_io_counters()[:2]

        self.network_tab = NetworkTab()
        self.process_tab = ProcessTab()

        self.tab_widget.addTab(self.network_tab, "Network Traffic")
        self.tab_widget.addTab(self.process_tab, "Running Processes")

        self.setCentralWidget(self.tab_widget)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_tabs)
        self.timer.start(1000)

        self.process_tab.process_clicked.connect(self.show_process_traffic)

        self.start_recording_button = QPushButton("Start Recording")
        self.start_recording_button.clicked.connect(self.start_recording)

        self.stop_recording_button = QPushButton("Stop Recording")
        self.stop_recording_button.clicked.connect(self.stop_recording)
        self.stop_recording_button.setEnabled(False)

        layout = QVBoxLayout()
        layout.addWidget(self.start_recording_button)
        layout.addWidget(self.stop_recording_button)
        layout.addStretch()

        widget = QWidget()
        widget.setLayout(layout)
        self.tab_widget.addTab(widget, "Recording")

        self.recording_directory = "recordings"
        self.current_recording_file = None

        self.process_graph_windows = {}
        
        self.last_bytes_sent, self.last_bytes_recv = self.start_bytes_sent, self.start_bytes_recv

    def update_tabs(self):
        global process_traffic_data, start_time

        # Update NetworkTab
        net_io = psutil.net_io_counters()
        current_time = time.time() - start_time
        overall_sent = net_io.bytes_sent - self.start_bytes_sent
        overall_received = net_io.bytes_recv - self.start_bytes_recv

        if overall_sent >= self.last_bytes_sent and overall_received >= self.last_bytes_recv:
            self.network_tab.update_plot(current_time, overall_sent - self.last_bytes_sent, overall_received - self.last_bytes_recv)

        self.last_bytes_sent, self.last_bytes_recv = overall_sent, overall_received  # Store the last sent and received values

        print(f"Current Time: {current_time}")
        print(f"Overall sent: {overall_sent}, Last bytes sent: {self.last_bytes_sent}")
        print(f"Overall received: {overall_received}, Last bytes received: {self.last_bytes_recv}")


        self.network_tab.update_plot(current_time, overall_sent - self.last_bytes_sent, overall_received - self.last_bytes_recv)

        self.start_bytes_sent, self.start_bytes_recv = net_io.bytes_sent, net_io.bytes_recv

        # Update ProcessTab
        process_names = self.process_tab.process_text.toPlainText().split('\n')
        process_list = [p for p in psutil.process_iter(['name', 'io_counters']) if p.info['name'] in process_names]

        for proc in process_list:
            if proc.info['io_counters']:
                sent = proc.info['io_counters'].write_bytes
                received = proc.info['io_counters'].read_bytes
                
                process_name = proc.info['name']
                if process_name not in process_traffic_data:
                    process_traffic_data[process_name] = {'times': [], 'sent': [], 'received': []}

                process_traffic_data[process_name]['times'].append(current_time)
                process_traffic_data[process_name]['sent'].append(sent)
                process_traffic_data[process_name]['received'].append(received)

        sorted_processes = sorted(
            [(proc_name, traffic_data) for proc_name, traffic_data in process_traffic_data.items()],
            key=lambda x: sum(x[1]['sent']) + sum(x[1]['received']), reverse=True)

        self.process_tab.update_process_tabs(sorted_processes[:4])

    def start_recording(self):
        global recording_enabled, recording_file
        recording_enabled = True

        if not os.path.exists(self.recording_directory):
            os.mkdir(self.recording_directory)

        recording_file = os.path.join(self.recording_directory, f"Recording_{time.time()}.txt")
        self.current_recording_file = recording_file

        self.start_recording_button.setEnabled(False)
        self.stop_recording_button.setEnabled(True)

    def stop_recording(self):
        global recording_enabled
        recording_enabled = False

        self.start_recording_button.setEnabled(True)
        self.stop_recording_button.setEnabled(False)

        QMessageBox.information(self, "Recording Finished", f"Recording data has been saved to {self.current_recording_file}")

    def show_process_traffic(self, process_name):
        if process_name in self.process_graph_windows:
            self.process_graph_windows[process_name].show()
        else:
            window = QMainWindow()
            canvas = AppCanvas(window)
            window.setCentralWidget(canvas)
            self.process_graph_windows[process_name] = window
            window.show()

        times = process_traffic_data[process_name]['times']
        sent = process_traffic_data[process_name]['sent']
        received = process_traffic_data[process_name]['received']

        self.process_graph_windows[process_name].centralWidget().plot(times, sent, received)


if __name__ == "__main__":
    qapp = QApplication(sys.argv)

    app = ApplicationWindow()
    app.show()

    sys.exit(qapp.exec_())
