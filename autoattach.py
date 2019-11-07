#!/usr/bin/python3

import re
import sys
import asyncio
import logging

import qubesadmin
import qubesadmin.events
import qubesadmin.devices
import qubesadmin.exc


DEV_TYPES = ["block", "usb"]

# This is VM where we will auto attach.
# This will come from a configuration file in production.
TARGET_VM = "buster-build"


class Device:
    def __init__(self, dev):
        self.dev_name = str(dev)
        self.ident = dev.ident
        self.description = dev.description
        self.devclass = dev.devclass
        self.attachments = set()
        self.backend_domain = dev.backend_domain.name

    def __str__(self):
        return self.dev_name

    def __eq__(self, other):
        return str(self) == str(other)


class LazyWorker:
    def __init__(self, qapp, dispatcher):
        self.dispatcher = dispatcher
        self.qapp = qapp
        self.vms = []
        self.devices = {}
        self.manually_removed = {}

        for devclass in DEV_TYPES:
            self.dispatcher.add_handler(
                "device-attach:" + devclass, self.device_attached
            )
            self.dispatcher.add_handler(
                "device-list-change:" + devclass, self.device_list_update
            )
            self.dispatcher.add_handler(
                "device-detach:" + devclass, self.device_detached
            )

        # Record all vms
        for vm in self.qapp.domains:
            if vm.klass != "AdminVM" and vm.is_running():
                self.vms.append(vm)

        self.initialize_dev_data()

    def initialize_dev_data(self):
        # list all devices
        for domain in self.qapp.domains:
            for devclass in DEV_TYPES:
                for device in domain.devices[devclass]:
                    self.devices[str(device)] = Device(device)

        # list existing device attachments
        for domain in self.qapp.domains:
            for devclass in DEV_TYPES:
                for device in domain.devices[devclass].attached():
                    dev = str(device)
                    if dev in self.devices:
                        # occassionally ghost UnknownDevices appear when a
                        # device was removed but not detached from a VM
                        self.devices[dev].attachments.add(domain.name)

    def device_attached(self, vm, _event, device, **_kwargs):
        if not vm.is_running() or device.devclass not in DEV_TYPES:
            return

        if str(device) not in self.devices:
            self.devices[str(device)] = Device(device)

        self.devices[str(device)].attachments.add(str(vm))
        logging.debug("Attached in VM: {0} DEVICE: {1}".format(str(vm), str(device)))

    def device_list_update(self, vm, _event, **_kwargs):
        """
        Everytime a device is attached to the hardware (laptop), this
        method will be called. The same will happen when a device will be detached
        from any other VM.

        """

        changed_devices = []

        # create list of all current devices from the changed VM
        try:
            for devclass in DEV_TYPES:
                for device in vm.devices[devclass]:
                    changed_devices.append(Device(device))
        except qubesadmin.exc.QubesException:
            changed_devices = []  # VM was removed

        for dev in changed_devices:
            if str(dev) not in self.devices:
                self.devices[str(dev)] = dev
                msg = "VM: {0} DEVICE: {1}".format(str(vm), str(dev))
                logging.debug(msg)
                if (
                    str(vm) == "sys-usb"
                    and re.match(".*sd[a-z]$", str(dev))
                    and str(dev) not in self.manually_removed
                ):
                    # attach to target vm
                    self.auto_attach(dev)

        dev_to_remove = [
            name
            for name, dev in self.devices.items()
            if dev.backend_domain == vm and name not in changed_devices
        ]
        for dev_name in dev_to_remove:
            logging.debug("Device removed: {0}".format(dev_name))
            del self.devices[dev_name]
            if dev_name in self.manually_removed:
                del self.manually_removed[dev_name]

    def device_detached(self, vm, _event, device, **_kwargs):
        if not vm.is_running():
            return

        device = str(device)
        # keep it to the manually removed list
        # this helps in future to not auto attach
        self.manually_removed[device] = True

    def auto_attach(self, device):
        "Add the device to our TARGET_VM"
        # First we will have to detach from the backend_domain
        for vm in device.attachments:
            try:
                assignment = qubesadmin.devices.DeviceAssignment(
                    device.backend_domain, device.ident, persistent=False
                )
                self.qapp.domains[vm].devices[device.devclass].detach(assignment)
            except qubesadmin.exc.QubesException as ex:
                logging.error("Failed to auto_attach {0}".format(ex))
                return

        # now attach to the TARGET_VM
        try:
            assignment = qubesadmin.devices.DeviceAssignment(
                device.backend_domain, device.ident, persistent=False
            )

            vm_to_attach = self.qapp.domains[TARGET_VM]
            vm_to_attach.devices[device.devclass].attach(assignment)

        except Exception as ex:  #
            logging.error("Failed to attach in the final step {0}".format(ex))


def main():
    qapp = qubesadmin.Qubes()
    dispatcher = qubesadmin.events.EventsDispatcher(qapp)

    lz = LazyWorker(qapp, dispatcher)

    loop = asyncio.get_event_loop()

    done, _ = loop.run_until_complete(
        asyncio.ensure_future(dispatcher.listen_for_events())
    )

    exit_code = 0

    for d in done:
        try:
            d.result()
        except Exception:
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
