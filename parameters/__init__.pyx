__author__ = 'Matthew Wardrop'
__author_email__ = 'mister dot <surname> at gmail'
__version__ = '0.9'

import sys
if sys.version_info.major == 3:
	text_type = str
else:
	text_type = (str,unicode)

import pyximport; pyximport.install()

import numpy as np

from .quantities import Quantity,SIQuantity
from .units import UnitsDispenser, Units, Unit
from .definitions import SIDispenser
from .parameters import Parameters, Bounds
