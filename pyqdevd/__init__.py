import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QSize

import qubesadmin

DEV_TYPES = ["block", "usb", "mic"]


class DeviceWidget(QWidget):
    def __init__(
        self,
        device,
        devclass,
        vms,
        msg_callback,
        connected=False,
        vmname="",
        assignment=None,
        domain=None,
    ):
        QWidget.__init__(self)
        name = device.description.replace("_", " ")
        self.device = device
        self.devicestatus = connected
        self.vmname = vmname
        self.domain = domain
        self.devclass = devclass
        self.assignment = assignment
        self.msg_callback = msg_callback
        self.layout = QHBoxLayout()

        # The name
        nameLabel = QLabel(name)
        nameLabel.setToolTip(device.ident)
        self.layout.addWidget(nameLabel)

        # The vms
        self.cbox = QComboBox()
        self.cbox.setStyleSheet("QComboBox { height: 40px;  }")
        self.cbox.addItems(vms)
        self.layout.addWidget(self.cbox)

        # button
        self.button = QPushButton("")

        if connected:
            self.button.setStyleSheet(
                "QPushButton { width: 50px; height: 40px; color: red; }"
            )
            self.button.setText("Disconnect")
            self.cbox.setCurrentText(vmname)
            self.cbox.setEnabled(False)
        else:
            self.button.setText("Connect")
            self.cbox.setEnabled(True)
            self.button.setStyleSheet(
                "QPushButton { width: 50px; height: 40px; color: green; }"
            )

        self.button.clicked.connect(self.clicked)
        self.layout.addWidget(self.button)
        self.setLayout(self.layout)

    def clicked(self):
        "Button clicked"
        vmname = self.cbox.currentText()
        self.button.setEnabled(False)
        self.button.repaint()
        if not self.devicestatus:
            assignment = qubesadmin.devices.DeviceAssignment(
                self.device.backend_domain, self.device.ident, persistent=False
            )
            dname = self.cbox.currentText()
            app = qubesadmin.Qubes()
            domain = app.domains[dname]
            domain.devices[self.devclass].attach(assignment)

            self.domain = domain
            self.vmname = dname
            self.assignment = assignment
            self.devicestatus = True

            self.msg_callback(
                "Connected {0} to {1}".format(self.device.description, vmname)
            )
            self.button.setText("Disconnect")
            self.button.setStyleSheet(
                "QPushButton { width: 50px; height: 40px; color: red; }"
            )
            self.cbox.setEnabled(False)
        else:
            self.domain.devices[self.devclass].detach(self.assignment)
            self.domain = None
            self.vmname = ""
            self.assignment = None
            self.devicestatus = False
            self.msg_callback(
                "Disconnected {0} from {1}".format(self.device.description, vmname)
            )
            self.button.setText("Connect")
            self.button.setStyleSheet(
                "QPushButton { width: 50px; height: 40px; color: green; }"
            )
            self.cbox.setEnabled(True)
        self.button.setEnabled(True)
        self.button.repaint()


class MainWindow(QMainWindow):
    "Application main window"

    def __init__(self):
        QMainWindow.__init__(self)

        self.app = qubesadmin.Qubes()

        # To hold the devices and their status
        self.devices = {}
        self.running_vms = []
        # widgets to refresh
        self.widgets = []

        self.setMinimumSize(QSize(600, 400))
        self.setWindowTitle("Qubes Devices")
        self.centralWidget = QWidget(self)
        self.setCentralWidget(self.centralWidget)

        self.gridLayout = QGridLayout(self)
        self.centralWidget.setLayout(self.gridLayout)

        self.refreshButton = QPushButton("Refresh")
        self.refreshButton.setStyleSheet("QPushButton { height: 50px;  }")
        self.refreshButton.clicked.connect(self.refresh_view)
        self.gridLayout.addWidget(self.refreshButton, 0, 0)

        self.gridLayout.addWidget(QLabel("Devices on the system", self), 1, 0)

        self.trayIcon = QSystemTrayIcon(self)
        self.trayIcon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))

        self.quitAction = QAction("Exit", self)
        self.quitAction.triggered.connect(qApp.quit)
        self.trayMenu = QMenu()
        self.trayMenu.addAction(self.quitAction)
        self.trayIcon.setContextMenu(self.trayMenu)
        self.trayIcon.activated.connect(self.view_toggle)
        self.trayIcon.show()
        self.refresh_view()

    def view_toggle(self, reason):
        "To handle clicks on the tray icon"
        if reason == 1:
            self.trayMenu.show()
            return
        if self.isVisible():
            self.hide()
        else:
            self.show()

    def closeEvent(self, event):
        "MainWindow closing event"
        event.ignore()
        self.hide()
        self.trayIcon.showMessage(
            "QDevD",
            "Application was minimized to Tray",
            QSystemTrayIcon.Information,
            2000,
        )

    def msg_show(self, text):
        self.trayIcon.showMessage("QDevD", text, QSystemTrayIcon.Information, 2000)

    def refresh_view(self):
        """
        Redo all device widgets
        """
        self.refreshButton.setEnabled(False)
        self.refreshButton.repaint()
        for w in self.widgets:
            w.hide()
            del w

        result = []
        devs = []
        # List of currently running vms
        self.running_vms = []
        # First get all the devices
        for domain in self.app.domains:
            if not domain.is_running():
                continue
            if domain.name != "dom0":
                self.running_vms.append(domain.name)

            # now the devices
            for devclass in DEV_TYPES:
                for dev in domain.devices[devclass].available():
                    devs.append((dev, devclass))

        for dev, devclass in devs:
            attached = False
            for domain in self.app.domains:
                if domain == dev.backend_domain:
                    continue

                if not domain.is_running():
                    continue

                for assignment in domain.devices[devclass].assignments():
                    if dev != assignment.device:
                        continue

                    # we found the domain and the assignment value
                    result.append((dev, devclass, domain.name, assignment, domain))
                    attached = True

            if not attached:
                result.append((dev, devclass))

        for value in result:
            self.addDevice(value)
        self.refreshButton.setEnabled(True)

    def addDevice(self, value):
        "Method to add device"
        widget = None
        if len(value) == 2:
            widget = DeviceWidget(value[0], value[1], self.running_vms, self.msg_show)
        else:
            widget = DeviceWidget(
                value[0],
                value[1],
                self.running_vms,
                self.msg_show,
                True,
                value[2],
                value[3],
                value[4],
            )
        self.widgets.append(widget)
        self.gridLayout.addWidget(widget)
        widget.show()


def main():
    app = QApplication(sys.argv)
    mainwindow = MainWindow()
    mainwindow.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
