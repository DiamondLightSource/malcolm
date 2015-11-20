from malcolm.devices.zebra2.zebra2 import Zebra2
import cProfile as profile

profile.runctx('Zebra2("Z", "localhost", 8888)', globals(), locals())
