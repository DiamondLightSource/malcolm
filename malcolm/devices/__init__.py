from malcolm.core import Device

class DetectorDriver(Device):
    pass


from malcolm.devices.dummydet import DummyDet
from malcolm.devices.hdf5writer import Hdf5Writer
from malcolm.devices.simdetectordriver import SimDetectorDriver
from malcolm.devices.dtacqdriver import DtacqDriver
from malcolm.devices.positionplugin import PositionPlugin
from malcolm.devices.progscan import ProgScan
from malcolm.devices.simdetector import SimDetector
from malcolm.devices.arpesscan import ArpesScan
from malcolm.devices.labscan import LabScan
