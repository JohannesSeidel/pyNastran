import numpy as np
#import warnings
#warnings.filterwarnings('ignore', 'missing __init__.py*')
#from pyNastran.gui.qt_version import qt_version
#if qt_version == 'pyqt4':
    #import PyQt4
#elif qt_version == 'pyqt5':
    #import PyQt5
#elif qt_version == 'pyside':
    #import PySide
#elif qt_version == 'pyside2':
    #import PySide2
#else:  # pragma: no cover
    #raise NotImplementedError(qt_version)

#if not IS_DEV:
    #from pyNastran.gui.menus.test_groups import *
from pyNastran.all_tests_no_gui import *


if __name__ == "__main__":  # pragma: no cover
    import unittest
    with np.errstate(divide='raise', over='raise', under='raise', invalid='raise'):
        unittest.main()
