#pylint: disable=R0913
"""
Defines the sub-OP2 class.  This should never be called outisde of the OP2 class.

 - OP2_Scalar(debug=False, log=None, debug_file=None)

   **Methods**
   - set_subcases(subcases=None)
   - set_transient_times(times)
   - read_op2(op2_filename=None, combine=False)
   - set_additional_generalized_tables_to_read(tables)
   - set_additional_result_tables_to_read(tables)
   - set_additional_matrices_to_read(matrices)

   **Attributes**
   - total_effective_mass_matrix
   - effective_mass_matrix
   - rigid_body_mass_matrix
   - modal_effective_mass_fraction
   - modal_participation_factors
   - modal_effective_mass
   - modal_effective_weight
   - set_as_msc()
   - set_as_optistruct()

   **Private Methods**
   - _get_table_mapper()
   - _not_available(data, ndata)
   - _table_crasher(data, ndata)
   - _table_passer(data, ndata)
   - _validate_op2_filename(op2_filename)
   - _create_binary_debug()
   - _make_tables()
   - _read_tables(table_name)
   - _skip_table(table_name)
   - _read_table_name(rewind=False, stop_on_failure=True)
   - _update_generalized_tables(tables)
   - _read_cmodext()
   - _read_cmodext_helper(marker_orig, debug=False)
   - _read_geom_table()
   - _finish()

"""
import os
from struct import Struct, unpack
from collections import defaultdict
from typing import List, Tuple, Dict, Union, Any

from numpy import array
import numpy as np
from cpylog import get_logger

from pyNastran import is_release, __version__
from pyNastran.f06.errors import FatalError
from pyNastran.op2.op2_interface.op2_reader import OP2Reader
from pyNastran.bdf.cards.params import PARAM

#============================

from pyNastran.op2.op2_interface.msc_tables import MSC_RESULT_TABLES, MSC_MATRIX_TABLES, MSC_GEOM_TABLES
from pyNastran.op2.op2_interface.nx_tables import NX_RESULT_TABLES, NX_MATRIX_TABLES, NX_GEOM_TABLES

from pyNastran.op2.tables.lama_eigenvalues.lama import LAMA
from pyNastran.op2.tables.oee_energy.onr import ONR
from pyNastran.op2.tables.ogf_gridPointForces.ogpf import OGPF

from pyNastran.op2.tables.oef_forces.oef import OEF
from pyNastran.op2.tables.oes_stressStrain.oes import OES
#from pyNastran.op2.tables.oes_stressStrain.oesm import OESM
from pyNastran.op2.tables.ogs_grid_point_stresses.ogs import OGS

from pyNastran.op2.tables.opg_appliedLoads.opg import OPG
from pyNastran.op2.tables.oqg_constraintForces.oqg import OQG
from pyNastran.op2.tables.oug.oug import OUG
from pyNastran.op2.tables.ogpwg import OGPWG
from pyNastran.op2.fortran_format import FortranFormat

from pyNastran.utils import is_binary_file

"""
ftp://161.24.15.247/Nastran2011/seminar/SEC04-DMAP_MODULES.pdf

Datablock	Type	Description
EFMFSMS	Matrix	6 x 1 Total Effective mass matrix
EFMASSS	Matrix	6 x 6 Effective mass matrix
RBMASS	Matrix	6 x 6 Rigid body mass matrix
EFMFACS	Matrix	6 X N Modal effective mass fraction matrix
MPFACS	Matrix	6 x N Modal participation factor matrix
MEFMASS	Matrix	6 x N Modal effective mass matrix
MEFWTS	Matrix	6 x N Modal effective weight matrix
RAFGEN	Matrix	N x M Generalized force matrix
RADEFMP	Matrix	N X U2 Effective inertia loads
BHH	Matrix	N x N Viscous damping matrix
K4HH	Matrix	N x N Structural damping matrix
RADAMPZ	Matrix	N x N equivalent viscous damping ratios
RADAMPG	Matrix	N X N equivalent structural damping ratio

LAMA	LAMA	Eigenvalue summary table
OGPWG	OGPWG	Mass properties output
OQMG1	OQMG	Modal MPC forces
RANCONS	ORGY1	Constraint mode element strain energy table
RANEATC	ORGY1	Attachment mode element strain energy table
RAGCONS	OGPFB	Constraint mode grid point force table
RAGEATC	OGPFB	Attachment mode grid point force table
RAPCONS	OES	Constraint mode ply stress table
RAPEATC	OES	Attachment mode ply stress table
RASCONS	OES	Constraint mode element stress table
RAECONS	OES	Constraint mode element strain table
RASEATC	OES	Attachment mode element stress table
RAEEATC	OES	Attachment mode element strain table
OES1C	OES	Modal Element Stress Table
OES1X	OES	Modal Element Stress Table
OSTR1C	OES	Modal Element Strain Table
OSTR1X	OSTR	Modal Element Strain Table
RAQCONS	OUG	Constraint mode MPC force table
RADCONS	OUG	Constraint mode displacement table
RADEFFM	OUG	Effective inertia displacement table
RAQEATC	OUG	Attachment mode  MPC force table
RADEATC	OUG	Attachment mode displacement table
OUGV1	OUG	Eigenvector Table
RAFCONS	OEF	Constraint mode element force table
RAFEATC	OEF	Attachment mode element force table
OEF1X	OEF	Modal Element Force Table
OGPFB1	OGPFB	Modal Grid Point Force Table
ONRGY1	ONRGY1	Modal Element Strain Energy Table
ONRGY2	ONRGY1

#--------------------

RADCONS - Displacement Constraint Mode
RADDATC - Displacement Distributed Attachment Mode
RADNATC - Displacement Nodal Attachment Mode
RADEATC - Displacement Equivalent Inertia Attachment Mode
RADEFFM - Displacement Effective Inertia Mode

RAECONS - Strain Constraint Mode
RAEDATC - Strain Distributed Attachment Mode
RAENATC - Strain Nodal Attachment Mode
RAEEATC - Strain Equivalent Inertia Attachment Mode

RAFCONS - Element Force Constraint Mode
RAFDATC - Element Force Distributed Attachment Mode
RAFNATC - Element Force Nodal Attachment Mode
RAFEATC - Element Force Equivalent Inertia Attachment Mode

RALDATC - Load Vector Used to Compute the Distributed Attachment M

RANCONS - Strain Energy Constraint Mode
RANDATC - Strain Energy Distributed Attachment Mode
RANNATC - Strain Energy Nodal Attachment Mode
RANEATC - Strain Energy Equivalent Inertia Attachment Mode

RAQCONS - Ply Strains Constraint Mode
RAQDATC - Ply Strains Distributed Attachment Mode
RAQNATC - Ply Strains Nodal Attachment Mode
RAQEATC - Ply Strains Equivalent Inertia Attachment Mode

RARCONS - Reaction Force Constraint Mode
RARDATC - Reaction Force Distributed Attachment Mode
RARNATC - Reaction Force Nodal Attachment Mode
RAREATC - Reaction Force Equivalent Inertia Attachment Mode

RASCONS - Stress Constraint Mode
RASDATC - Stress Distributed Attachment Mode
RASNATC - Stress Nodal Attachment Mode
RASEATC - Stress Equivalent Inertia Attachment Mode

RAPCONS - Ply Stresses Constraint Mode
RAPDATC - Ply Stresses Distributed Attachment Mode
RAPNATC - Ply Stresses Nodal Attachment Mode
RAPEATC - Ply Stresses Equivalent Inertia Attachment Mode

RAGCONS - Grid Point Forces Constraint Mode
RAGDATC - Grid Point Forces Distributed Attachment Mode
RAGNATC - Grid Point Forces Nodal Attachment Mode
RAGEATC - Grid Point Forces Equivalent Inertia Attachment Mode

RADEFMP - Displacement PHA^T * Effective Inertia Mode

RADAMPZ - Viscous Damping Ratio Matrix
RADAMPG - Structural Damping Ratio Matrix

RAFGEN  - Generalized Forces
BHH     - Modal Viscous Damping Matrix
K4HH    - Modal Structural Damping Matrix
"""
GEOM_TABLES = MSC_GEOM_TABLES + NX_GEOM_TABLES

AUTODESK_MATRIX_TABLES = [
    #b'BELM',
    b'KELM',
    #b'MELM',
] # type: List[bytes]
# this will be split later
TEST_MATRIX_TABLES = [b'ATB', b'BTA', b'MYDOF']

RESULT_TABLES = NX_RESULT_TABLES + MSC_RESULT_TABLES
MATRIX_TABLES = NX_MATRIX_TABLES + MSC_MATRIX_TABLES + AUTODESK_MATRIX_TABLES + TEST_MATRIX_TABLES + [b'MEFF']

#GEOM_TABLES = MSC_GEOM_TABLES
#RESULT_TABLES = MSC_RESULT_TABLES
#MATRIX_TABLES = MSC_MATRIX_TABLES

# TODO: these are weird...
#   RPOSTS1, MAXRATI, RESCOMP, PDRMSG
INT_PARAMS_1 = [
    b'POST', b'OPPHIPA', b'OPPHIPB', b'GRDPNT', b'RPOSTS1', b'BAILOUT',
    b'COUPMASS', b'CURV', b'INREL', b'MAXRATI', b'OG',
    b'S1AM', b'S1M', b'DDRMM', b'MAXIT', b'PLTMSG', b'LGDISP', b'NLDISP',
    b'OUNIT2K', b'OUNIT2M', b'RESCOMP', b'PDRMSG', b'LMODES', b'USETPRT',
    b'NOCOMPS', b'OPTEXIT', b'RSOPT', b'GUSTAERO', b'MPTUNIT',
    b'USETSEL', b'NASPRT', b'DESPCH', b'DESPCH1', b'COMPARE', b'DBNBLKS', b'NEWSEQ', b'OLDSEQ',
    b'METHCMRS', b'NOFISR', b'KGGCPCH', b'ERROR', b'DBCDIAG', b'GPECT', b'LSTRN',
    b'DBDROPT', b'SEOP2CV', b'IRES', b'SNORMPRT', b'DBDRNL', b'VMOPT',
    b'OSWPPT', b'KDAMP', b'KDAMPFL', b'MATNL', b'MPCX', b'GEOMPLT', b'NOELOP',
    b'NOGPF', b'PROUT', b'SUPER', b'LGDIS', b'EST', b'SEP1XOVR',
    b'FRSEID', b'HRSEID', b'LRSEID', b'MODACC', b'XFLAG', b'TSTATIC',
    b'NASPDV', b'RMXCRT', b'RMXTRN', b'DBCLEAN', b'LANGLE', b'SEMAPPRT',
    b'FIXEDB', b'AMGOK', b'ASING', b'CNSTRT', b'CURVPLOT', b'CYCIO',
    b'CYCSEQ', b'DBDICT', b'DBINIT', b'DBSET1', b'DBSET2', b'DBSET3', b'DBSET4',
    b'DBSORT', b'DOPT', b'FACTOR', b'ALTSHAPE', b'MODTRK', b'IFTM', b'INRLM',
    b'KINDEX', b'KMIN', b'KMAX', b'LARGEDB', b'LOADINC', b'LOADING', b'LOOP',
    b'LOOPID', b'MODEL', b'MOREK', b'NEWDYN', b'NFECI', b'NINTPTS',
    b'NLAYERS', b'NOELOF', b'NOMSGSTR', b'NONCUP', b'NUMOUT', b'NUMOUT1', b'NUMOUT2',
    b'OPGTKG', b'OPPHIB', b'OUTOPT', b'PKRSP', b'RSPECTRA', b'RSPRINT',
    b'S1G', b'SCRSPEC', b'SEMAPOPT', b'SEQOUT', b'SESEF', b'SKPAMG', b'SKPAMP',
    b'SLOOPID', b'SOLID', b'SPCGEN', b'SRTELTYP', b'SRTOPT', b'START', b'SUBID',
    b'SUBSKP', b'TABID', b'TESTNEG', b'BDMNCON',

    # not defined in qrg...
    b'NT', b'PNCHDB', b'DLOAD', b'NLOAD', b'NOAP', b'NOCMPFLD', b'NODATA',
    b'NODJE', b'NOMECH', b'NOSDR1', b'NOSHADE', b'NOSORT1', b'NOTRED',
    b'NSEGS', b'OLDELM', b'OPADOF', b'OUTPUT', b'P1', b'P2', b'P3', b'PCHRESP',
    b'PLOT', b'PLOTSUP', b'PRTPCH', b'RADLIN', b'RESDUAL', b'S1', b'SDATA',
    b'SEFINAL', b'SEMAP1', b'SKPLOAD', b'SKPMTRX', b'SOLID1', b'SSG3',
    b'PEDGEP', b'ACMSPROC', b'ACMSSEID', b'ACOUS', b'ACOUSTIC', b'ADJFLG',
    b'ADJLDF', b'AEDBCP', b'AESRNDM', b'ARCSIGNS', b'ATVUSE', b'BADMESH', b'BCHNG',
    b'BCTABLE', b'ROTCSV', b'ROTGPF',
]
FLOAT_PARAMS_1 = [
    b'K6ROT', b'WTMASS', b'SNORM', b'PATVER', b'MAXRATIO', b'EPSHT',
    b'SIGMA', b'TABS', b'EPPRT', b'AUNITS', b'BOLTFACT', b'LMSCAL',
    'DSZERO', b'G', b'GFL', b'LFREQ', b'HFREQ', b'ADPCON',
    b'W3', b'W4', b'W3FL', b'W4FL', b'PREFDB',
    b'EPZERO', b'DSZERO', b'TINY', b'TOLRSC',
    b'FRSPD', b'HRSPD', b'LRSPD', b'MTRFMAX', b'ROTCMRF', b'MTRRMAX',
    b'LAMLIM', b'BIGER', b'BIGER1', b'BIGER2', b'CLOSE',
    b'EPSBIG', b'EPSMALC', b'EPSMALU', b'HIRES', b'KDIAG', b'MACH', b'VREF',
    b'STIME', b'TESTSE', b'LFREQFL', b'Q', b'ADPCONS', b'AFNORM', b'AFZERO',

    # not defined
    b'PRPA', b'PRPHIVZ', b'PRPJ', b'PRRULV', b'RMAX', b'ADJFRQ', b'ARF',
    b'ARS',
]
FLOAT_PARAMS_2 = [
    b'BETA', b'CB1', b'CB2', b'CK1', b'CK2', b'CK3', b'CK41', b'CK42',
    b'CM1', b'CM2',
    b'G2', b'G4', b'G5', b'G6', b'G7', b'G8', b'G9', b'G10', b'G12', b'G13',
    b'ALPHA1', b'ALPHA2', b'APPF',
]
INT_PARAMS_2 = [b'APPI',]
DOUBLE_PARAMS_1 = [] # b'Q'
STR_PARAMS_1 = [
    b'POSTEXT', b'PRTMAXIM', b'AUTOSPC', b'OGEOM', b'PRGPST',
    b'RESVEC', b'RESVINER', b'ALTRED', b'OGPS', b'OIBULK', b'OMACHPR',
    b'UNITSYS', b'F56', b'OUGCORD', b'OGEM', b'EXTSEOUT',
    b'CDIF', b'SUPAERO', b'RSCON', b'AUTOMPC', b'DBCCONV',
    b'AUTOSPRT', b'PBRPROP', b'OMID', b'HEATSTAT', b'SECOMB', b'ELEMITER',
    b'ELITASPC', b'DBCONV', b'SHLDAMP', b'COMPMATT', b'SPCSTR', b'ASCOUP',
    b'PRTRESLT', b'SRCOMPS', b'CHECKOUT', b'SEMAP', b'AESMETH', b'RESVALT',
    b'ROTSYNC', b'SYNCDAMP', b'PRGPOST', b'WMODAL', b'SDAMPUP',
    b'COLPHEXA', b'CHKOUT', b'CTYPE', b'DBNAME', b'VUHEXA', b'VUPENTA', b'VUTETRA',
    b'MESH', b'OPTION', b'PRINT', b'SENAME', b'MECHFIX', b'RMXTRAN', b'FLEXINV',
    b'ADSTAT', b'ACOUT', b'ACSYM', b'ACTYPE', b'ADBX', b'AUTOSEEL',
    b'RDSPARSE',

    # part of param, checkout
    b'PRTBGPDT', b'PRTCSTM', b'PRTEQXIN', b'PRTGPDT',
    b'PRTGPL', b'PRTGPTT', b'PRTMGG', b'PRTPG',

    # superelements
    b'EXTOUT', b'SESDAMP',

    # TODO: remove these as they're in the matrix test and are user
    #       defined PARAMs; arguably all official examples should just work
    # TODO: add an option for custom PARAMs
    b'ADB', b'AEDB', b'MREDUC', b'OUTDRM', b'OUTFORM', b'REDMETH', b'DEBUG',
    b'AEDBX', b'AERO', b'AUTOSUP0', b'AXIOPT',
]

class OP2_Scalar(LAMA, ONR, OGPF,
                 OEF, OES, OGS, OPG, OQG, OUG, OGPWG, FortranFormat):
    """
    Defines an interface for the Nastran OP2 file.
    """
    @property
    def total_effective_mass_matrix(self):
        """6x6 matrix"""
        return self.matrices['EFMFSMS']

    @property
    def effective_mass_matrix(self):
        """6x6 matrix"""
        return self.matrices['EFMASSS']

    @property
    def rigid_body_mass_matrix(self):
        """6x6 matrix"""
        return self.matrices['RBMASS']

    @property
    def modal_effective_mass_fraction(self):
        """6xnmodes matrix"""
        return self.matrices['EFMFACS']#.dataframe

    @property
    def modal_participation_factors(self):
        """6xnmodes matrix"""
        return self.matrices['MPFACS']#.dataframe

    @property
    def modal_effective_mass(self):
        """6xnmodes matrix"""
        return self.matrices['MEFMASS']#.dataframe

    @property
    def modal_effective_weight(self):
        """6xnmodes matrix"""
        return self.matrices['MEFWTS']#.dataframe

    @property
    def matrix_tables(self):
        return MATRIX_TABLES

    def set_as_nx(self):
        self.is_nx = True
        self.is_msc = False
        self.is_autodesk = False
        self.is_optistruct = False
        self._nastran_format = 'nx'

    def set_as_msc(self):
        self.is_nx = False
        self.is_msc = True
        self.is_autodesk = False
        self.is_optistruct = False
        self._nastran_format = 'msc'

    def set_as_autodesk(self):
        self.is_nx = False
        self.is_msc = False
        self.is_autodesk = True
        self.is_optistruct = False
        self._nastran_format = 'autodesk'

    def set_as_optistruct(self):
        self.is_nx = False
        self.is_msc = False
        self.is_autodesk = False
        self.is_optistruct = True
        self._nastran_format = 'optistruct'

    def __init__(self, debug=False, log=None, debug_file=None):
        """
        Initializes the OP2_Scalar object

        Parameters
        ----------
        debug : bool; default=False
            enables the debug log and sets the debug in the logger
        log : Log()
            a logging object to write debug messages to
            (.. seealso:: import logging)
        debug_file : str; default=None (No debug)
            sets the filename that will be written to

        """
        assert isinstance(debug, bool), 'debug=%r' % debug

        self.log = get_logger(log, 'debug' if debug else 'info')
        self._count = 0
        self.op2_filename = None
        self.bdf_filename = None
        self.f06_filename = None
        self.des_filename = None
        self.h5_filename = None
        self._encoding = 'utf8'

        #: should a MATPOOL "symmetric" matrix be stored as symmetric
        #: it takes double the RAM, but is easier to use
        self.apply_symmetry = True

        LAMA.__init__(self)
        ONR.__init__(self)
        OGPF.__init__(self)

        OEF.__init__(self)
        OES.__init__(self)
        #OESM.__init__(self)
        OGS.__init__(self)

        OPG.__init__(self)
        OQG.__init__(self)
        OUG.__init__(self)
        OGPWG.__init__(self)
        FortranFormat.__init__(self)

        self.is_vectorized = False
        self._close_op2 = True

        self.result_names = set()

        self.grid_point_weight = {}
        self.words = []
        self.debug = debug
        self._last_comment = None
        #self.debug = True
        #self.debug = False
        #debug_file = None
        if debug_file is None:
            self.debug_file = None
        else:
            assert isinstance(debug_file, str), debug_file
            self.debug_file = debug_file

        self.op2_reader = OP2Reader(self)

    def set_subcases(self, subcases=None):
        """
        Allows you to read only the subcases in the list of isubcases

        Parameters
        ----------
        subcases : List[int, ...] / int; default=None->all subcases
            list of [subcase1_ID,subcase2_ID]

        """
        #: stores the set of all subcases that are in the OP2
        #self.subcases = set()
        if subcases is None or subcases == []:
            #: stores if the user entered [] for isubcases
            self.is_all_subcases = True
            self.valid_subcases = []
        else:
            #: should all the subcases be read (default=True)
            self.is_all_subcases = False

            if isinstance(subcases, int):
                subcases = [subcases]

            #: the set of valid subcases -> set([1,2,3])
            self.valid_subcases = set(subcases)
        self.log.debug("set_subcases - subcases = %s" % self.valid_subcases)

    def set_transient_times(self, times):  # TODO this name sucks...
        """
        Takes a dictionary of list of times in a transient case and
        gets the output closest to those times.

        Examples
        --------
        >>> times = {subcase_id_1: [time1, time2],
                     subcase_id_2: [time3, time4]}

        .. warning:: I'm not sure this still works...

        """
        expected_times = {}
        for (isubcase, etimes) in times.items():
            etimes = list(times)
            etimes.sort()
            expected_times[isubcase] = array(etimes)
        self.expected_times = expected_times

    def _get_table_mapper(self):
        """gets the dictionary of function3 / function4"""

        # MSC table mapper
        table_mapper = {
            # per NX
            b'OESVM1' : [self._read_oes1_3, self._read_oes1_4],    # isat_random
            b'OESVM1C' : [self._read_oes1_3, self._read_oes1_4],   # isat_random
            b'OSTRVM1' : [self._read_oes1_3, self._read_ostr1_4],   # isat_random
            b'OSTRVM1C' : [self._read_oes1_3, self._read_ostr1_4],  # isat_random

            b'OSTRVM2' : [self._read_oes2_3, self._read_ostr2_4],

            b'OESVM2' : [self._read_oes2_3, self._read_oes2_4],    # big random
            b'OES2C' : [self._read_oes2_3, self._read_oes2_4],
            b'OSTR2' : [self._read_oes2_3, self._read_ostr2_4], # TODO: disable
            b'OSTR2C' : [self._read_oes2_3, self._read_ostr2_4],
            #b'OES2C' : [self._table_passer, self._table_passer], # stress
            #b'OSTR2' : [self._table_passer, self._table_passer],  # TODO: enable
            #b'OSTR2C' : [self._table_passer, self._table_passer],

            b'OTEMP1' : [self._read_otemp1_3, self._read_otemp1_4],
            # --------------------------------------------------------------------------
            # MSC TABLES
            # common tables

            # unorganized
            b'RADCONS': [self._read_oug1_3, self._read_oug_4], # Displacement Constraint Mode (OUG)
            b'RADEFFM': [self._read_oug1_3, self._read_oug_4], # Displacement Effective Inertia Mode (OUG)
            b'RADEATC': [self._read_oug1_3, self._read_oug_4], # Displacement Equivalent Inertia Attachment mode (OUG)

            # broken - isat_launch_100hz.op2 - wrong numwide
            # spc forces
            b'RAQCONS': [self._read_oqg1_3, self._read_oqg_4], # Constraint mode MPC force table (OQG)
            b'RAQEATC': [self._read_oqg1_3, self._read_oqg_4], # Attachment mode MPC force table (OQG)
            #b'RAQCONS': [self._table_passer, self._table_passer], # temporary
            #b'RAQEATC': [self._table_passer, self._table_passer], # temporary

            # element forces
            b'RAFCONS': [self._read_oef1_3, self._read_oef1_4], # Element Force Constraint Mode (OEF)
            b'RAFEATC': [self._read_oef1_3, self._read_oef1_4], # Element Force Equivalent Inertia Attachment mode (OEF)
            #b'RAFCONS': [self._table_passer, self._table_passer], # temporary
            #b'RAFEATC': [self._table_passer, self._table_passer], # temporary

            # grid point forces
            b'RAGCONS': [self._read_ogpf1_3, self._read_ogpf1_4], # Grid Point Forces Constraint Mode (OGPFB)
            b'RAGEATC': [self._read_ogpf1_3, self._read_ogpf1_4], # Grid Point Forces Equivalent Inertia Attachment mode (OEF)
            #b'RAGCONS': [self._table_passer, self._table_passer], # Grid Point Forces Constraint Mode (OGPFB)
            #b'RAGEATC': [self._table_passer, self._table_passer], # Grid Point Forces Equivalent Inertia Attachment mode (OEF)

            # stress
            b'RAPCONS': [self._read_oes1_3, self._read_oes1_4], # Constraint mode ply stress table (OES)
            b'RAPEATC': [self._read_oes1_3, self._read_oes1_4], # Attachment mode ply stress table (OES)
            #b'RAPCONS': [self._table_passer, self._table_passer], # Constraint mode ply stress table (OES)
            #b'RAPEATC': [self._table_passer, self._table_passer], # Attachment mode ply stress table (OES)

            # stress
            b'RASCONS': [self._read_oes1_3, self._read_oes1_4], # Stress Constraint Mode (OES)
            b'RASEATC': [self._read_oes1_3, self._read_oes1_4], # Stress Equivalent Inertia Attachment mode (OES)
            #b'RASCONS': [self._table_passer, self._table_passer], # temporary
            #b'RASEATC': [self._table_passer, self._table_passer], # temporary

            # strain
            b'RAEEATC': [self._read_oes1_3, self._read_ostr1_4], # Strain Equivalent Inertia Attachment mode (OES)
            b'RAECONS': [self._read_oes1_3, self._read_ostr1_4], # Strain Constraint Mode (OSTR)
            #b'RAEEATC': [self._table_passer, self._table_passer], # temporary
            #b'RAECONS': [self._table_passer, self._table_passer], # temporary

            # strain energy
            b'RANEATC' : [self._read_onr1_3, self._read_onr1_4], # Strain Energy Equivalent Inertia Attachment mode (ORGY1)
            b'RANCONS': [self._read_onr1_3, self._read_onr1_4], # Constraint mode element strain energy table (ORGY1)
            #b'RANEATC': [self._table_passer, self._table_passer], # Strain Energy Equivalent Inertia Attachment mode (ORGY1)
            #b'RANCONS': [self._table_passer, self._table_passer], # Constraint mode element strain energy table (ORGY1)


            b'R1TABRG': [self._table_passer, self.op2_reader.read_r1tabrg],
            #b'TOL': [self._table_passer, self._table_passer],

            b'MATPOOL': [self._table_passer, self._table_passer], # DMIG bulk data entries

            # this comment may refer to CSTM?
            #F:\work\pyNastran\examples\Dropbox\pyNastran\bdf\cards\test\test_mass_01.op2
            #F:\work\pyNastran\examples\matpool\gpsc1.op2
            b'AXIC': [self._table_passer, self._table_passer],

            b'RSOUGV1': [self._table_passer, self._table_passer],
            b'RESOES1': [self._table_passer, self._table_passer],
            b'RESEF1' : [self._table_passer, self._table_passer],
            b'DESCYC' : [self._table_passer, self._table_passer],
            #b'AEMONPT' : [self._read_aemonpt_3, self._read_aemonpt_4],
            #=======================
            # OEF
            # element forces
            #b'OEFITSTN' : [self._table_passer, self._table_passer], # works
            b'OEFITSTN' : [self._read_oef1_3, self._read_oef1_4],
            b'OEFIT' : [self._read_oef1_3, self._read_oef1_4],  # failure indices
            b'OEF1X' : [self._read_oef1_3, self._read_oef1_4],  # element forces at intermediate stations
            b'OEF1'  : [self._read_oef1_3, self._read_oef1_4],  # element forces or heat flux
            b'HOEF1' : [self._read_oef1_3, self._read_oef1_4],  # element heat flux
            b'DOEF1' : [self._read_oef1_3, self._read_oef1_4],  # scaled response spectra - forces

            # off force
            b'OEF2' : [self._read_oef2_3, self._read_oef2_4],  # element forces or heat flux
            #=======================
            # OQG
            # spc forces
            # OQG1/OQGV1 - spc forces in the nodal frame
            # OQP1 - scaled response spectra - spc-forces
            b'OQG1' : [self._read_oqg1_3, self._read_oqg_4],
            b'OQG2' : [self._read_oqg2_3, self._read_oqg_4],

            b'OQGV1' : [self._read_oqg1_3, self._read_oqg_4],
            b'OQGV2' : [self._read_oqg2_3, self._read_oqg_4],

            b'OQP1' : [self._read_oqg1_3, self._read_oqg_4],
            b'OQP2' : [self._read_oqg2_3, self._read_oqg_4],

            # SPC/MPC tables depending on table_code
            # SPC - NX/MSC
            # MPC - MSC
            b'OQGATO1' : [self._read_oqg1_3, self._read_oqg_4],
            b'OQGCRM1' : [self._read_oqg1_3, self._read_oqg_4],
            b'OQGPSD1' : [self._read_oqg1_3, self._read_oqg_4],
            b'OQGRMS1' : [self._read_oqg1_3, self._read_oqg_4],
            b'OQGNO1'  : [self._read_oqg1_3, self._read_oqg_4],

            b'OQGATO2' : [self._read_oqg2_3, self._read_oqg_4],
            b'OQGCRM2' : [self._read_oqg2_3, self._read_oqg_4],
            b'OQGPSD2' : [self._read_oqg2_3, self._read_oqg_4],
            b'OQGRMS2' : [self._table_passer, self._table_passer],  # buggy on isat random
            b'OQGNO2'  : [self._table_passer, self._table_passer],  # buggy on isat random
            #b'OQGRMS2' : [self._read_oqg2_3, self._read_oqg_4],  # buggy on isat random
            #b'OQGNO2'  : [self._read_oqg2_3, self._read_oqg_4],  # buggy on isat random

            #=======================
            # MPC Forces
            # these are NX tables

            # OQGM1 - mpc forces in the nodal frame
            b'OQMG1'   : [self._read_oqg1_3, self._read_oqg_mpc_forces],
            b'OQMATO1' : [self._read_oqg1_3, self._read_oqg_mpc_ato],
            b'OQMCRM1' : [self._read_oqg1_3, self._read_oqg_mpc_crm],
            b'OQMPSD1' : [self._read_oqg1_3, self._read_oqg_mpc_psd],
            b'OQMRMS1' : [self._read_oqg1_3, self._read_oqg_mpc_rms],
            b'OQMNO1'  : [self._read_oqg1_3, self._read_oqg_mpc_no],

            b'OQMG2'   : [self._read_oqg2_3, self._read_oqg_mpc_forces], # big random
            b'OQMATO2' : [self._read_oqg2_3, self._read_oqg_mpc_ato],
            b'OQMCRM2' : [self._read_oqg2_3, self._read_oqg_mpc_crm],
            b'OQMPSD2' : [self._read_oqg2_3, self._read_oqg_mpc_psd],
            b'OQMRMS2' : [self._table_passer, self._table_passer],  # buggy on isat random
            b'OQMNO2'  : [self._table_passer, self._table_passer],  # buggy on isat random
            #b'OQMRMS2' : [self._read_oqg2_3, self._read_oqg_mpc_rms],  # buggy on isat random
            #b'OQMNO2'  : [self._read_oqg2_3, self._read_oqg_mpc_no],  # buggy on isat random

            #=======================
            # OPG
            # applied loads
            b'OPG1'  : [self._read_opg1_3, self._read_opg1_4],  # applied loads in the nodal frame
            b'OPGV1' : [self._read_opg1_3, self._read_opg1_4],  # solution set applied loads?
            b'OPNL1' : [self._read_opg1_3, self._read_opg1_4],  # nonlinear loads
            b'OCRPG' : [self._read_opg1_3, self._read_opg1_4],  # post-buckling loads

            b'OPG2' : [self._read_opg2_3, self._read_opg1_4],   # applied loads in the nodal frame
            b'OPNL2' : [self._read_opg2_3, self._read_opg1_4],  # nonlinear loads

            b'OPGATO1' : [self._read_opg1_3, self._read_opg1_4],
            b'OPGCRM1' : [self._read_opg1_3, self._read_opg1_4],
            b'OPGPSD1' : [self._read_opg1_3, self._read_opg1_4],
            b'OPGRMS1' : [self._read_opg1_3, self._read_opg1_4],
            b'OPGNO1'  : [self._read_opg1_3, self._read_opg1_4],

            b'OPGATO2' : [self._read_opg2_3, self._read_opg1_4],
            b'OPGCRM2' : [self._read_opg2_3, self._read_opg1_4],
            b'OPGPSD2' : [self._read_opg2_3, self._read_opg1_4],
            #b'OPGRMS2' : [self._table_passer, self._table_passer],
            #b'OPGNO2'  : [self._table_passer, self._table_passer],
            b'OPGRMS2' : [self._read_opg2_3, self._read_opg1_4],
            b'OPGNO2'  : [self._read_opg2_3, self._read_opg1_4],
            #=======================
            # OGPFB1
            # grid point forces
            b'OGPFB1' : [self._read_ogpf1_3, self._read_ogpf1_4],  # grid point forces

            #=======================
            # ONR/OEE
            # strain energy density
            b'ONRGY'  : [self._read_onr1_3, self._read_onr1_4],
            b'ONRGY1' : [self._read_onr1_3, self._read_onr1_4],  # strain energy density
            b'ONRGY2':  [self._read_onr2_3, self._read_onr1_4],
            #b'ONRGY2':  [self._table_passer, self._table_passer],
            #===========================================================
            # OES
            # stress
            # OES1C - Table of composite element stresses or strains in SORT1 format
            # OESRT - Table of composite element ply strength ratio. Output by SDRCOMP
            b'OES1X1' : [self._read_oes1_3, self._read_oes1_4], # stress - nonlinear elements
            b'OES1'   : [self._read_oes1_3, self._read_oes1_4], # stress - linear only
            b'OES1X'  : [self._read_oes1_3, self._read_oes1_4], # element stresses at intermediate stations & nonlinear stresses
            b'OES1C'  : [self._read_oes1_3, self._read_oes1_4], # stress - composite
            b'OESCP'  : [self._read_oes1_3, self._read_oes1_4], # stress - nonlinear???
            b'OESRT'  : [self._read_oes1_3, self._read_oes1_4], # ply strength ratio

            # strain
            b'OSTR1' : [self._read_oes1_3, self._read_ostr1_4],  # strain - autodesk/9zk6b5uuo.op2
            b'OSTR1X'  : [self._read_oes1_3, self._read_ostr1_4],  # strain - isotropic
            b'OSTR1C'  : [self._read_oes1_3, self._read_ostr1_4],  # strain - composite
            b'OESTRCP' : [self._read_oes1_3, self._read_ostr1_4],

            # special nonlinear tables
            # OESNLBR - Slideline stresses
            # OESNLXD - Nonlinear transient stresses
            # OESNLXR - Nonlinear stress
            #           Table of nonlinear element stresses in SORT1 format and appended for all subcases

            b'OESNLXR' : [self._read_oes1_3, self._read_oes1_4],  # nonlinear stresses
            b'OESNLXD' : [self._read_oes1_3, self._read_oes1_4],  # nonlinear transient stresses
            b'OESNLBR' : [self._read_oes1_3, self._read_oes1_4],
            b'OESNL1X' : [self._read_oes1_3, self._read_oes1_4],

            b'OESNL2' : [self._read_oes2_3, self._read_oes2_4],
            b'OESNLXR2' : [self._read_oes2_3, self._read_oes2_4],
            b'OESNLBR2' : [self._read_oes2_3, self._read_oes2_4],
            #b'OESNLXR2' : [self._table_passer, self._table_passer],
            #b'OESNLBR2' : [self._table_passer, self._table_passer],

            # off stress
            b'OES2'    : [self._read_oes2_3, self._read_oes2_4],  # stress - linear only - disabled; need better tests
            #b'OES2'    : [self._table_passer, self._table_passer],  # stress - linear only - disabled; need better tests

            #b'OESPSD2C' : [self._table_passer, self._table_passer],
            #b'OSTPSD2C' : [self._table_passer, self._table_passer],
            #=======================

            # off strain
            b'OSTRATO1' : [self._read_oes1_3, self._read_ostr1_4],
            b'OSTRCRM1' : [self._read_oes1_3, self._read_ostr1_4],
            b'OSTRPSD1' : [self._read_oes1_3, self._read_ostr1_4],
            b'OSTRRMS1' : [self._read_oes1_3, self._read_ostr1_4], # isat_random
            b'OSTRNO1' : [self._read_oes1_3, self._read_ostr1_4],  # isat_random

            b'OSTRATO2' : [self._read_oes2_3, self._read_ostr2_4],
            b'OSTRCRM2' : [self._read_oes2_3, self._read_ostr2_4],
            b'OSTRPSD2' : [self._read_oes2_3, self._read_ostr2_4],
            b'OSTRRMS2' : [self._table_passer, self._table_passer],  # buggy on isat random
            b'OSTRNO2' : [self._table_passer, self._table_passer],  # buggy on isat random
            #b'OSTRRMS2' : [self._read_oes2_3, self._read_ostr2_4],  # buggy on isat random
            #b'OSTRNO2' : [self._read_oes2_3, self._read_ostr2_4],  # buggy on isat random

            b'OSTRMS1C' : [self._read_oes1_3, self._read_ostr1_4], # isat_random
            b'OSTNO1C' : [self._read_oes1_3, self._read_ostr1_4],  # isat_random

            #=======================
            # OUG
            # displacement/velocity/acceleration/eigenvector/temperature
            b'OUG1'    : [self._read_oug1_3, self._read_oug_4],  # displacements in nodal frame
            # OVG1?
            b'OAG1'    : [self._read_oug1_3, self._read_oug_4],  # accelerations in nodal frame

            b'OUGV1'   : [self._read_oug1_3, self._read_oug_4],  # displacements in nodal frame
            b'BOUGV1'  : [self._read_oug1_3, self._read_oug_4],  # OUG1 on the boundary???
            b'OUGV1PAT': [self._read_oug1_3, self._read_oug_4],  # OUG1 + coord ID
            b'OUPV1'   : [self._read_oug1_3, self._read_oug_4],  # scaled response spectra - displacement
            b'TOUGV1'  : [self._read_oug1_3, self._read_oug_4],  # grid point temperature
            b'ROUGV1'  : [self._read_oug1_3, self._read_oug_4],  # relative OUG
            b'OPHSA'   : [self._read_oug1_3, self._read_oug_4],  # Displacement output table in SORT1
            b'OUXY1'   : [self._read_oug1_3, self._read_oug_4],  # Displacements in SORT1 format for h-set or d-set.

            b'OUGV2'   : [self._read_oug2_3, self._read_oug_4],  # displacements in nodal frame
            b'ROUGV2'  : [self._read_oug2_3, self._read_oug_4],  # relative OUG
            b'OUXY2'   : [self._read_oug2_3, self._read_oug_4],  # Displacements in SORT2 format for h-set or d-set.

            #F:\work\pyNastran\examples\Dropbox\move_tpl\sbuckl2a.op2
            b'OCRUG' : [self._read_oug1_3, self._read_oug_4],  # post-buckling displacement

            b'OPHIG' : [self._read_oug1_3, self._read_oug_4],  # eigenvectors in basic coordinate system
            b'BOPHIG' : [self._read_oug1_3, self._read_oug_4],  # eigenvectors in basic coordinate system
            b'BOPHIGF' : [self._read_oug1_3, self._read_oug_4],  # Eigenvectors in the basic coordinate system for the fluid portion of the model.
            b'BOPHIGS' : [self._read_oug1_3, self._read_oug_4],  # Eigenvectors in the basic coordinate system for the structural portion of the model.

            b'BOPG1' : [self._read_opg1_3, self._read_opg1_4],  # applied loads in basic coordinate system

            b'OUGATO1' : [self._read_oug1_3, self._read_oug_ato],
            b'OUGCRM1' : [self._read_oug1_3, self._read_oug_crm],
            b'OUGPSD1' : [self._read_oug1_3, self._read_oug_psd],
            b'OUGRMS1' : [self._read_oug1_3, self._read_oug_rms],
            b'OUGNO1'  : [self._read_oug1_3, self._read_oug_no],

            b'OUGATO2' : [self._read_oug2_3, self._read_oug_ato],
            b'OUGCRM2' : [self._read_oug2_3, self._read_oug_crm],
            b'OUGPSD2' : [self._read_oug2_3, self._read_oug_psd],
            b'OUGRMS2' : [self._table_passer, self._table_passer],  # buggy on isat random
            b'OUGNO2'  : [self._table_passer, self._table_passer],  # buggy on isat random
            #b'OUGRMS2' : [self._read_oug2_3, self._read_oug_rms],  # buggy on isat random
            #b'OUGNO2'  : [self._read_oug2_3, self._read_oug_no],  # buggy on isat random

            #=======================
            # extreme values of the respective table
            b'OUGV1MX' : [self._table_passer, self._table_passer],
            b'OEF1MX' : [self._table_passer, self._table_passer],
            b'OES1MX' : [self._table_passer, self._table_passer],

            #=======================
            # contact
            b'OQGCF1' : [self._table_passer, self._table_passer], # Contact force at grid point.
            b'OQGCF2' : [self._table_passer, self._table_passer], # Contact force at grid point.

            b'OSPDS1' : [self._table_passer, self._table_passer],  # Final separation distance.
            b'OSPDS2' : [self._table_passer, self._table_passer],

            b'OSPDSI1' : [self._table_passer, self._table_passer], # Initial separation distance.
            b'OSPDSI2' : [self._table_passer, self._table_passer], # Output contact separation distance results.

            b'OBC1' : [self._table_passer, self._table_passer],
            b'OBC2' : [self._table_passer, self._table_passer], # Contact pressures and tractions at grid points.

            # Glue normal and tangential tractions at grid point in basic coordinate system
            b'OBG1' : [self._table_passer, self._table_passer],
            b'OBG2' : [self._table_passer, self._table_passer],

            b'OQGGF1' : [self._table_passer, self._table_passer], # Glue forces at grid point in basic coordinate system
            b'OQGGF2' : [self._table_passer, self._table_passer],
            #=======================
            # OGPWG
            # grid point weight
            b'OGPWG'  : [self._read_ogpwg_3, self._read_ogpwg_4],  # grid point weight
            b'OGPWGM' : [self._read_ogpwg_3, self._read_ogpwg_4],  # modal? grid point weight

            #=======================
            # OGS
            # grid point stresses
            b'OGS1' : [self._read_ogs1_3, self._read_ogs1_4],  # grid point stresses
            #b'OGS2' : [self._read_ogs1_3, self._read_ogs1_4],  # grid point stresses
            #=======================
            # eigenvalues
            b'BLAMA' : [self._read_buckling_eigenvalue_3, self._read_buckling_eigenvalue_4], # buckling eigenvalues
            b'CLAMA' : [self._read_complex_eigenvalue_3, self._read_complex_eigenvalue_4],   # complex eigenvalues
            b'LAMA'  : [self._read_real_eigenvalue_3, self._read_real_eigenvalue_4],         # eigenvalues
            b'LAMAS' : [self._read_real_eigenvalue_3, self._read_real_eigenvalue_4],         # eigenvalues-structure
            b'LAMAF' : [self._read_real_eigenvalue_3, self._read_real_eigenvalue_4],         # eigenvalues-fluid

            # ===========================geom passers===========================
            # geometry
            b'GEOM1' : [self._table_passer, self._table_passer], # GEOM1-Geometry-related bulk data
            b'GEOM2' : [self._table_passer, self._table_passer], # GEOM2-element connectivity and SPOINT-related data
            b'GEOM3' : [self._table_passer, self._table_passer], # GEOM3-Static and thermal loads
            b'GEOM4' : [self._table_passer, self._table_passer], # GEOM4-constraints, DOF membership entries, MPC, and R-type element data

            # superelements
            b'GEOM1S' : [self._table_passer, self._table_passer],  # GEOMx + superelement
            b'GEOM2S' : [self._table_passer, self._table_passer],
            b'GEOM3S' : [self._table_passer, self._table_passer],
            b'GEOM4S' : [self._table_passer, self._table_passer],

            b'GEOM1VU' : [self._table_passer, self._table_passer],
            b'GEOM2VU' : [self._table_passer, self._table_passer],
            b'BGPDTVU' : [self._table_passer, self._table_passer],

            b'GEOM1N' : [self._table_passer, self._table_passer],
            b'GEOM2N' : [self._table_passer, self._table_passer],
            b'GEOM3N' : [self._table_passer, self._table_passer],
            b'GEOM4N' : [self._table_passer, self._table_passer],

            b'GEOM1OLD' : [self._table_passer, self._table_passer],
            b'GEOM2OLD' : [self._table_passer, self._table_passer],
            b'GEOM3OLD' : [self._table_passer, self._table_passer],
            b'GEOM4OLD' : [self._table_passer, self._table_passer],

            b'EPT' : [self._table_passer, self._table_passer],  # elements
            b'EPTS' : [self._table_passer, self._table_passer],  # elements - superelements
            b'EPTOLD' : [self._table_passer, self._table_passer],

            b'MPT' : [self._table_passer, self._table_passer],  # materials
            b'MPTS' : [self._table_passer, self._table_passer],  # materials - superelements

            b'DYNAMIC' : [self._table_passer, self._table_passer],
            b'DYNAMICS' : [self._table_passer, self._table_passer],
            b'DIT' : [self._table_passer, self._table_passer],
            b'DITS' : [self._table_passer, self._table_passer],
            b'AXIC' : [self._table_passer, self._table_passer],
            # =========================end geom passers=========================

            # ===passers===
            #b'EQEXIN': [self._table_passer, self._table_passer],
            #b'EQEXINS': [self._table_passer, self._table_passer],

            b'GPDT' : [self._table_passer, self._table_passer],     # grid points?
            b'BGPDT' : [self._table_passer, self._table_passer],    # basic grid point defintion table
            b'BGPDTS' : [self._table_passer, self._table_passer],
            b'BGPDTOLD' : [self._table_passer, self._table_passer],

            b'PVT' : [self._read_pvto_3, self._read_pvto_4], # PVT - Parameter Variable Table
            b'PVTS' : [self._read_pvto_3, self._read_pvto_4], # ???
            b'PVT0' : [self._read_pvto_3, self._read_pvto_4],  # user parameter value table
            b'TOLD' : [self._table_passer, self._table_passer],
            b'CASECC' : [self._table_passer, self._table_passer],  # case control deck

            b'STDISP' : [self._table_passer, self._table_passer], # matrix?
            b'AEDISP' : [self._table_passer, self._table_passer], # matrix?
            #b'TOLB2' : [self._table_passer, self._table_passer], # matrix?

            # EDT - element deformation, aerodynamics, p-element, divergence analysis,
            #       and iterative solver input (includes SET1 entries)
            b'EDT' : [self._table_passer, self._table_passer],
            b'EDTS' : [self._table_passer, self._table_passer],

            b'FOL' : [self._table_passer, self._table_passer],
            b'PERF' : [self._table_passer, self._table_passer],
            b'VIEWTB' : [self._table_passer, self._table_passer],   # view elements

            # DSCMCOL - Correlation table for normalized design sensitivity coefficient matrix.
            #           Output by DSTAP2.
            # DBCOPT - Design optimization history table for
            b'CONTACT' : [self._table_passer, self._table_passer],
            b'CONTACTS' : [self._table_passer, self._table_passer],
            b'OEKE1' : [self._table_passer, self._table_passer],
            b'DSCMCOL' : [self._table_passer, self._table_passer],
            b'DBCOPT' : [self._table_passer, self._table_passer],
            #b'FRL0': [self._table_passer, self._table_passer],  # frequency response list

            #==================================
            # modal participation factors
            # OFMPF2M Table of fluid mode participation factors by normal mode.
            b'OFMPF2M' : [self._read_mpf_3, self._read_mpf_4],
            # OLMPF2M Load mode participation factors by normal mode.
            b'OLMPF2M' : [self._read_mpf_3, self._read_mpf_4],
            # OPMPF2M Panel mode participation factors by normal mode.
            b'OPMPF2M' : [self._read_mpf_3, self._read_mpf_4],
            # OPMPF2M Panel mode participation factors by normal mode.
            b'OSMPF2M' : [self._read_mpf_3, self._read_mpf_4],
            # OGMPF2M Grid mode participation factors by normal mode.
            b'OGPMPF2M' : [self._read_mpf_3, self._read_mpf_4],

            #OFMPF2E Table of fluid mode participation factors by excitation frequencies.
            #OSMPF2E Table of structure mode participation factors by excitation frequencies.
            #OPMPF2E Table of panel mode participation factors by excitation frequencies.
            #OLMPF2E Table of load mode participation factors by excitation frequencies.
            #OGMPF2E Table of grid mode participation factors by excitation frequencies.

            # velocity
            b'OVGATO1' : [self._read_oug1_3, self._read_oug_ato],
            b'OVGCRM1' : [self._read_oug1_3, self._read_oug_crm],
            b'OVGPSD1' : [self._read_oug1_3, self._read_oug_psd],
            b'OVGRMS1' : [self._read_oug1_3, self._read_oug_rms],
            b'OVGNO1'  : [self._read_oug1_3, self._read_oug_no],

            b'OVGATO2' : [self._read_oug2_3, self._read_oug_ato],
            b'OVGCRM2' : [self._read_oug2_3, self._read_oug_crm],
            b'OVGPSD2' : [self._read_oug2_3, self._read_oug_psd],
            #b'OVGRMS2' : [self._table_passer, self._table_passer],
            #b'OVGNO2'  : [self._table_passer, self._table_passer],
            b'OVGRMS2' : [self._read_oug2_3, self._read_oug_rms],
            b'OVGNO2'  : [self._read_oug2_3, self._read_oug_no],

            #==================================
            #b'GPL': [self._table_passer, self._table_passer],
            #b'OMM2' : [self._table_passer, self._table_passer],  # max/min table - kinda useless
            b'ERRORN' : [self._table_passer, self._table_passer],  # p-element error summary table
            #==================================

            b'EDOM' : [self._table_passer, self._table_passer],
            b'OUG2T' : [self._table_passer, self._table_passer],

            # acceleration
            b'OAGATO1' : [self._read_oug1_3, self._read_oug_ato],
            b'OAGCRM1' : [self._read_oug1_3, self._read_oug_crm],
            b'OAGPSD1' : [self._read_oug1_3, self._read_oug_psd],
            b'OAGRMS1' : [self._read_oug1_3, self._read_oug_rms],
            b'OAGNO1'  : [self._read_oug1_3, self._read_oug_no],

            b'OAGATO2' : [self._read_oug2_3, self._read_oug_ato],
            b'OAGCRM2' : [self._read_oug2_3, self._read_oug_crm],
            b'OAGPSD2' : [self._read_oug2_3, self._read_oug_psd],
            #b'OAGRMS2' : [self._table_passer, self._table_passer],
            #b'OAGNO2'  : [self._table_passer, self._table_passer],
            b'OAGRMS2' : [self._read_oug2_3, self._read_oug_rms],
            b'OAGNO2'  : [self._read_oug2_3, self._read_oug_no],

            # stress
            b'OESATO1' : [self._read_oes1_3, self._read_oes1_4],
            b'OESCRM1' : [self._read_oes1_3, self._read_oes1_4],
            b'OESPSD1' : [self._read_oes1_3, self._read_oes1_4],
            b'OESRMS1' : [self._read_oes1_3, self._read_oes1_4],
            b'OESNO1'  : [self._read_oes1_3, self._read_oes1_4],

            # OESXRM1C : Composite element RMS stresses in SORT1 format for random analysis that includes von Mises stress output.
            b'OESXRMS1' : [self._read_oes1_3, self._read_oes1_4],
            b'OESXRM1C' : [self._read_oes1_3, self._read_oes1_4],
            b'OESXNO1' : [self._read_oes1_3, self._read_oes1_4],
            b'OESXNO1C' : [self._read_oes1_3, self._read_oes1_4],


            b'OESATO2' : [self._read_oes2_3, self._read_oes2_4],
            b'OESCRM2' : [self._read_oes2_3, self._read_oes2_4],
            b'OESPSD2' : [self._read_oes2_3, self._read_oes2_4],
            #b'OESRMS2' : [self._read_oes1_3, self._read_oes1_4],  # buggy on isat random
            #b'OESNO2'  : [self._read_oes1_3, self._read_oes1_4],  # buggy on isat random
            b'OESRMS2' : [self._table_passer, self._table_passer],  # buggy on isat random
            b'OESNO2'  : [self._table_passer, self._table_passer],  # buggy on isat random

            # force
            b'OEFATO1' : [self._read_oef1_3, self._read_oef1_4],
            b'OEFCRM1' : [self._read_oef1_3, self._read_oef1_4],
            b'OEFPSD1' : [self._read_oef1_3, self._read_oef1_4],
            b'OEFRMS1' : [self._read_oef1_3, self._read_oef1_4],
            b'OEFNO1'  : [self._read_oef1_3, self._read_oef1_4],

            b'OEFATO2' : [self._read_oef2_3, self._read_oef2_4],
            b'OEFCRM2' : [self._read_oef2_3, self._read_oef2_4],
            b'OEFPSD2' : [self._read_oef2_3, self._read_oef2_4],
            #b'OEFRMS2' : [self._read_oef2_3, self._read_oef2_4], # buggy on isat random
        }
        if self.is_nx and 0:
            table_mapper2 = {
                #b'OUGRMS2' : [self._table_passer, self._table_passer],  # buggy on isat random
                #b'OUGNO2'  : [self._table_passer, self._table_passer],  # buggy on isat random
                b'OUGRMS2' : [self._read_oug2_3, self._read_oug_rms],  # buggy on isat random
                b'OUGNO2'  : [self._read_oug2_3, self._read_oug_no],  # buggy on isat random

                #b'OQMRMS2' : [self._table_passer, self._table_passer],  # buggy on isat random
                #b'OQMNO2'  : [self._table_passer, self._table_passer],  # buggy on isat random
                b'OQMRMS2' : [self._read_oqg2_3, self._read_oqg_mpc_rms],  # buggy on isat random
                b'OQMNO2'  : [self._read_oqg2_3, self._read_oqg_mpc_no],  # buggy on isat random

                #b'OSTRRMS2' : [self._table_passer, self._table_passer],  # buggy on isat random
                #b'OSTRNO2' : [self._table_passer, self._table_passer],  # buggy on isat random
                b'OSTRRMS2' : [self._read_oes2_3, self._read_ostr2_4],  # buggy on isat random
                b'OSTRNO2' : [self._read_oes2_3, self._read_ostr2_4],  # buggy on isat random

                b'OESRMS2' : [self._read_oes1_3, self._read_oes1_4],  # buggy on isat random
                b'OESNO2'  : [self._read_oes1_3, self._read_oes1_4],  # buggy on isat random
                #b'OESRMS2' : [self._table_passer, self._table_passer],  # buggy on isat random
                #b'OESNO2'  : [self._table_passer, self._table_passer],  # buggy on isat random

                b'OEFNO2'  : [self._read_oef2_3, self._read_oef2_4],
                #b'OEFNO2' : [self._table_passer, self._table_passer], # buggy on isat_random_steve2.op2
            }
            for key, value in table_mapper2.items():
                table_mapper[key] = value
            #table_mapper.update(table_mapper2)
        return table_mapper

    def _read_mpf_3(self, data, ndata: int) -> int:
        """reads table 3 (the header table)

        OFMPF2E Table of fluid mode participation factors by excitation frequencies.
        OFMPF2M Table of fluid mode participation factors by normal mode.
        OSMPF2E Table of structure mode participation factors by excitation frequencies.
        OSMPF2M Table of structure mode participation factors by normal mode.
        OPMPF2E Table of panel mode participation factors by excitation frequencies.
        OPMPF2M Table of panel mode participation factors by normal mode.
        OLMPF2E Table of load mode participation factors by excitation frequencies.
        OLMPF2M Table of load mode participation factors by normal mode.
        OGMPF2E Table of grid mode participation factors by excitation frequencies.
        OGMPF2M Table of grid mode participation factors by normal mode.
        """
        #self._set_times_dtype()
        self.nonlinear_factor = np.nan
        self.is_table_1 = True
        self.is_table_2 = False
        unused_three = self.parse_approach_code(data)
        self.words = [
            'approach_code', 'table_code', '???', 'isubcase',
            '???', '???', '???', 'random_code',
            'format_code', 'num_wide', '???', '???',
            'acoustic_flag', '???', '???', '???',
            '???', '???', '???', '???',
            '???', '???', 'thermal', '???',
            '???', 'Title', 'subtitle', 'label']

        ## random code
        self.random_code = self.add_data_parameter(data, 'random_code', b'i', 8, False)

        ## format code
        self.format_code = self.add_data_parameter(data, 'format_code', b'i', 9, False)

        ## number of words per entry in record
        self.num_wide = self.add_data_parameter(data, 'num_wide', b'i', 10, False)

        ## acoustic pressure flag
        self.acoustic_flag = self.add_data_parameter(data, 'acoustic_flag', b'i', 13, False)

        ## thermal flag; 1 for heat transfer, 0 otherwise
        self.thermal = self.add_data_parameter(data, 'thermal', b'i', 23, False)

        #if self.analysis_code == 1:   # statics / displacement / heat flux
            ## load set number
            #self.lsdvmn = self.add_data_parameter(data, 'lsdvmn', b'i', 5, False)
            #self.data_names = self.apply_data_code_value('data_names', ['lsdvmn'])
            #self.setNullNonlinearFactor()
        #elif self.analysis_code == 2:  # real eigenvalues
            ## mode number
            #self.mode = self.add_data_parameter(data, 'mode', b'i', 5)
            ## eigenvalue
            #self.eign = self.add_data_parameter(data, 'eign', b'f', 6, False)
            ## mode or cycle .. todo:: confused on the type - F1???
            #self.mode_cycle = self.add_data_parameter(data, 'mode_cycle', b'i', 7, False)
            #self.update_mode_cycle('mode_cycle')
            #self.data_names = self.apply_data_code_value('data_names', ['mode', 'eign', 'mode_cycle'])
        #elif self.analysis_code == 3: # differential stiffness
            #self.lsdvmn = self.get_values(data, b'i', 5) ## load set number
            #self.data_code['lsdvmn'] = self.lsdvmn
        #elif self.analysis_code == 4: # differential stiffness
            #self.lsdvmn = self.get_values(data, b'i', 5) ## load set number
        if self.analysis_code == 5:   # frequency
            # frequency
            self.node_id = self.add_data_parameter(data, 'node_id', b'i', 5, fix_device_code=True)
            self.data_names = self.apply_data_code_value('data_names', ['node_id'])
            #self.freq = self.add_data_parameter(data, 'freq', b'f', 5)
            #self.data_names = self.apply_data_code_value('data_names', ['freq'])
        #elif self.analysis_code == 6:  # transient
            ## time step
            #self.dt = self.add_data_parameter(data, 'dt', b'f', 5)
            #self.data_names = self.apply_data_code_value('data_names', ['dt'])
        #elif self.analysis_code == 7:  # pre-buckling
            ## load set number
            #self.lsdvmn = self.add_data_parameter(data, 'lsdvmn', b'i', 5)
            #self.data_names = self.apply_data_code_value('data_names', ['lsdvmn'])
        #elif self.analysis_code == 8:  # post-buckling
            ## load set number
            #self.lsdvmn = self.add_data_parameter(data, 'lsdvmn', b'i', 5)
            ## real eigenvalue
            #self.eigr = self.add_data_parameter(data, 'eigr', b'f', 6, False)
            #self.data_names = self.apply_data_code_value('data_names', ['lsdvmn', 'eigr'])
        #elif self.analysis_code == 9:  # complex eigenvalues
            ## mode number
            #self.mode = self.add_data_parameter(data, 'mode', b'i', 5)
            ## real eigenvalue
            #self.eigr = self.add_data_parameter(data, 'eigr', b'f', 6, False)
            ## imaginary eigenvalue
            #self.eigi = self.add_data_parameter(data, 'eigi', b'f', 7, False)
            #self.data_names = self.apply_data_code_value('data_names', ['mode', 'eigr', 'eigi'])
        #elif self.analysis_code == 10:  # nonlinear statics
            ## load step
            #self.lftsfq = self.add_data_parameter(data, 'lftsfq', b'f', 5)
            #self.data_names = self.apply_data_code_value('data_names', ['lftsfq'])
        #elif self.analysis_code == 11:  # old geometric nonlinear statics
            ## load set number
            #self.lsdvmn = self.add_data_parameter(data, 'lsdvmn', b'i', 5)
            #self.data_names = self.apply_data_code_value('data_names', ['lsdvmn'])
        #elif self.analysis_code == 12:  # contran ? (may appear as aCode=6)  --> straight from DMAP...grrr...
            ## load set number
            #self.lsdvmn = self.add_data_parameter(data, 'lsdvmn', b'i', 5)
            #self.data_names = self.apply_data_code_value('data_names', ['lsdvmn'])
        else:
            msg = f'invalid analysis_code...analysis_code={self.analysis_code}\ndata={self.data_code}'
            raise RuntimeError(msg)

        #print self.code_information()
        #
        self.fix_format_code()
        if self.num_wide == 8:
            self.format_code = 1
            self.data_code['format_code'] = 1
        else:
            #self.fix_format_code()
            if self.format_code == 1:
                self.format_code = 2
                self.data_code['format_code'] = 2
            assert self.format_code in [2, 3], self.code_information()

        self._parse_thermal_code()
        if self.is_debug_file:
            self.binary_debug.write('  approach_code  = %r\n' % self.approach_code)
            self.binary_debug.write('  tCode          = %r\n' % self.tCode)
            self.binary_debug.write('  isubcase       = %r\n' % self.isubcase)
        self._read_title(data)
        self._write_debug_bits()

    def _read_mpf_4(self, data, ndata):
        """unused"""
        if self.read_mode == 1: # or self.table_name_str not in ['OFMPF2M']:
            return ndata
        #print(self.table_name_str, ndata, self.num_wide)  # 176
        #self.show_ndata(100, types='ifs')

        structi = Struct('fiff')
        nelements = ndata // 16
        ndev = ndata % 16
        assert ndev == 0, ndev

        for i in range(nelements):
            datai = data[i*16 : (i+1)*16]
            freq, dunno_int, mag, phase = structi.unpack(datai)
            assert dunno_int == 2, str(self.node_id, freq, dunno_int, mag, phase)
            #print(self.node_id, freq, dunno_int, mag, phase)
        #print()
        if self.isubtable == -4:
            self.log.warning('%s results were read, but not saved' % self.table_name_str)
        return ndata

    def _read_pvto_3(self, data, ndata):
        """unused"""
        raise RuntimeError(self.read_mode)

    def _read_pvto_4(self, data, ndata):
        """reads PARAM cards"""
        if self.read_mode == 1:
            return ndata

        iloc = self.f.tell()
        try:
            ndata2 = self._read_pvto_4_helper(data, ndata)
        except Exception as e:
            self.log.error(str(e))
            if 'dev' in __version__:
                raise  # only for testing
            self.f.seek(iloc)
            ndata2 = ndata
        return ndata2

    def _read_pvto_4_helper(self, data, ndata):
        """reads PARAM cards"""
        nvalues = ndata // 4
        assert ndata % 4 == 0, ndata

        structs8 = Struct(b'8s')
        #struct2s8 = Struct(b'4s8s')
        struct2i = Struct(b'ii')
        struct2f = Struct(b'ff')
        struct2d = Struct(b'dd')
        i = 0

        #print('---------------------------')
        while i < nvalues:
            #print('*i=%s nvalues=%s' % (i, nvalues))
            word = data[i*4:(i+2)*4].rstrip()
            #print('word=%r' % word)
            #word = s8.unpack(word)[0]#.decode(self._encoding)

            # the first two entries are typically trash, then we can get values
            if word in INT_PARAMS_1:
                slot = data[(i+2)*4:(i+4)*4]
                value = struct2i.unpack(slot)[1]
                i += 4
            elif word in FLOAT_PARAMS_1:
                slot = data[(i+2)*4:(i+4)*4]
                value = struct2f.unpack(slot)[1]
                i += 4
            elif word in FLOAT_PARAMS_2:
                slot = data[(i+3)*4:(i+5)*4]
                value = struct2f.unpack(slot)
                i += 5
            elif word in INT_PARAMS_2:
                slot = data[(i+3)*4:(i+5)*4]
                value = struct2i.unpack(slot)
                i += 5
            elif word in DOUBLE_PARAMS_1:
                slot = data[(i+1)*4:(i+8)*4]
                try:
                    value = struct2d.unpack(slot)[1]
                except:
                    print(word)
                    raise
                i += 8
            #elif word in [b'VUHEXA']:
                #self.show_data(data[i*4:(i+5)*4], types='ifs', endian=None)
                #aaa
            elif word in STR_PARAMS_1:
                i += 3
                slot = data[i*4:(i+2)*4]
                value = structs8.unpack(slot)[0].decode('latin1').rstrip()
                i += 2
            else:
                self.show_data(data[i*4:(i+4)*4], types='ifsd')
                self.show_data(data[i*4+4:i*4+i*4+12], types='ifsd')
                raise NotImplementedError('%r is not a supported PARAM' % word)

            key = word.decode('latin1')
            #print(key, value)
            self.params[key] = PARAM(key, [value], comment='')
        return nvalues

    def _not_available(self, data, ndata):
        """testing function"""
        if ndata > 0:
            raise RuntimeError('this should never be called...'
                               'table_name=%r len(data)=%s' % (self.table_name, ndata))

    def _table_crasher(self, data, ndata):
        """auto-table crasher"""
        if self.is_debug_file:
            self.binary_debug.write('  crashing table = %s\n' % self.table_name)
            raise NotImplementedError(self.table_name)
        return ndata

    def _table_passer(self, data, ndata):
        """auto-table skipper"""
        if self.is_debug_file:
            self.binary_debug.write('  skipping table = %s\n' % self.table_name)
        if self.table_name not in GEOM_TABLES and self.isubtable > -4:
            self.log.warning('    skipping table: %s' % self.table_name_str)
        if not is_release and self.isubtable > -4:
            if self.table_name in GEOM_TABLES and not self.make_geom:
                pass
            else:
                print('dont skip table %r' % self.table_name_str)
                raise RuntimeError('dont skip table %r' % self.table_name_str)
        return ndata

    def _validate_op2_filename(self, op2_filename):
        """
        Pops a GUI if the op2_filename hasn't been set.

        Parameters
        ----------
        op2_filename : str
            the filename to check (None -> gui)

        Returns
        -------
        op2_filename : str
            a valid file string

        """
        if op2_filename is None:
            from pyNastran.utils.gui_io import load_file_dialog
            wildcard_wx = "Nastran OP2 (*.op2)|*.op2|" \
                "All files (*.*)|*.*"
            wildcard_qt = "Nastran OP2 (*.op2);;All files (*)"
            title = 'Please select a OP2 to load'
            op2_filename, unused_wildcard_level = load_file_dialog(
                title, wildcard_wx, wildcard_qt, dirname='')
            assert op2_filename is not None, op2_filename
        return op2_filename

    def _create_binary_debug(self):
        """Instatiates the ``self.binary_debug`` variable/file"""
        if hasattr(self, 'binary_debug') and self.binary_debug is not None:
            self.binary_debug.close()
            del self.binary_debug

        self.is_debug_file, self.binary_debug = create_binary_debug(
            self.op2_filename, self.debug_file, self.log)

    def read_op2(self, op2_filename=None, combine=False, load_as_h5=False, h5_file=None, mode=None):
        """
        Starts the OP2 file reading

        Parameters
        ----------
        op2_filename : str
            the op2 file
        combine : bool; default=True
            True : objects are isubcase based
            False : objects are (isubcase, subtitle) based;
                    will be used for superelements regardless of the option
        load_as_h5 : default=None
            False : don't setup the h5_file
            True : loads the op2 as an h5 file to save memory
                   stores the result.element/data attributes in h5 format
        h5_file : h5File; default=None
            None : ???
            h5File : ???

        +--------------+-----------------------+
        | op2_filename | Description           |
        +--------------+-----------------------+
        |     None     | a dialog is popped up |
        +--------------+-----------------------+
        |    string    | the path is used      |
        +--------------+-----------------------+
        """
        fname = os.path.splitext(op2_filename)[0]
        self.op2_filename = op2_filename
        self.bdf_filename = fname + '.bdf'
        self.f06_filename = fname + '.f06'
        self.des_filename = fname + '.des'
        self.h5_filename = fname + '.h5'

        self.op2_reader.load_as_h5 = load_as_h5
        if load_as_h5:
            h5_file = None
            import h5py
            self.h5_file = h5py.File(self.h5_filename, 'w')
            self.op2_reader.h5_file = self.h5_file

        self._count = 0
        if self.read_mode == 1:
            #sr = list(self._results.saved)
            #sr.sort()
            #self.log.debug('_results.saved = %s' % str(sr))
            #self.log.info('_results.saved = %s' % str(sr))
            pass

        if self.read_mode != 2:
            op2_filename = self._validate_op2_filename(op2_filename)
            self.log.info('op2_filename = %r' % op2_filename)
            if not is_binary_file(op2_filename):
                if os.path.getsize(op2_filename) == 0:
                    raise IOError('op2_filename=%r is empty.' % op2_filename)
                raise IOError('op2_filename=%r is not a binary OP2.' % op2_filename)

        self._create_binary_debug()
        self._setup_op2()
        self.op2_reader.read_nastran_version(mode)

        _op2 = self.op2_reader.op2
        data = _op2.f.read(4)
        _op2.f.seek(_op2.n)
        if len(data) == 0:
            raise FatalError('There was a Nastran FATAL Error.  Check the F06.\n'
                             'No tables exist...check for a license issue')

        #=================
        table_name = self.op2_reader._read_table_name(rewind=True, stop_on_failure=False)
        if table_name is None:
            raise FatalError('There was a Nastran FATAL Error.  Check the F06.\n'
                             'No tables exist...check for a license issue')

        self._make_tables()
        table_names = self._read_tables(table_name)

        self.close_op2(force=False)
        #self.remove_unpickable_data()
        return table_names

    def close_op2(self, force=True):
        """closes the OP2 and debug file"""
        if self.is_debug_file:
            self.binary_debug.write('-' * 80 + '\n')
            self.binary_debug.write('f.tell()=%s\ndone...\n' % self.f.tell())
            self.binary_debug.close()

        if self._close_op2 or force:
            if self.f is not None:
                # can happen if:
                #  - is ascii file
                self.f.close()
            del self.binary_debug
            del self.f
            self._cleanup_data_members()
            self._cleanup_words()
            #self.op2_reader.h5_file.close()

    def _cleanup_words(self):
        """
        Remove internal parameters that are not useful and just clutter
        the object attributes.
        """
        words = [
            'isubcase', 'int3', '_table4_count', 'nonlinear_factor',
            'is_start_of_subtable', 'superelement_adaptivity_index',
            'thermal_bits', 'is_vectorized', 'pval_step', #'_frequencies',
            '_analysis_code_fmt', 'isubtable', '_data_factor', 'sort_method',
            'acoustic_flag', 'approach_code', 'format_code_original',
            'element_name', 'sort_bits', 'code', 'n', 'use_vector', 'ask',
            'stress_bits', 'expected_times', 'table_code', 'sort_code',
            'is_all_subcases', 'num_wide', '_table_mapper', 'label',
            'apply_symmetry',
            'words', 'device_code', 'table_name', '_count', 'additional_matrices',
            # 350
            'data_names', '_close_op2',
            'op2_reader',
            # 74
            'generalized_tables',
            # 124
            'is_table_1', 'is_table_2', 'ntotal', 'element_mapper',
            'is_debug_file', 'debug_file',
            '_results', 'skip_undefined_matrices',
            # 140
            #---------------------------------------------------------
            # dont remove...
            # make_geom, title, read_mode
            # result_names, op2_results

        ]
        for word in words:
            if hasattr(self, word):
                delattr(self, word)

    def _setup_op2(self):
        """
        Does preliminary op2 tasks like:
          - open the file
          - set the endian
          - preallocate some struct objects

        """
        #: file index
        self.n = 0
        self.table_name = None

        if not hasattr(self, 'f') or self.f is None:
            #: the OP2 file object
            self.f = open(self.op2_filename, 'rb')
            #: the endian in bytes
            self._endian = None
            #: the endian in unicode
            self._uendian = None
            flag_data = self.f.read(20)
            self.f.seek(0)

            if unpack(b'>5i', flag_data)[0] == 4:
                self._uendian = '>'
                self._endian = b'>'
            elif unpack(b'<5i', flag_data)[0] == 4:
                self._uendian = '<'
                self._endian = b'<'
            #elif unpack(b'<ii', flag_data)[0] == 4:
                #self._endian = b'<'
            else:
                # Matrices from test show
                # (24, 10, 10, 6, 2) before the Matrix Name...
                #self.show_data(flag_data, types='iqlfsld', endian='<')
                #print('----------')
                #self.show_data(flag_data, types='iqlfsld', endian='>')
                raise FatalError('cannot determine endian')
        else:
            self.op2_reader._goto(self.n)

        if self.read_mode == 1:
            self._set_structs()

    def _make_tables(self):
        return
        #global RESULT_TABLES, NX_RESULT_TABLES, MSC_RESULT_TABLES
        #table_mapper = self._get_table_mapper()
        #RESULT_TABLES = table_mapper.keys()

    def _read_tables(self, table_name: bytes) -> List[bytes]:
        """
        Reads all the geometry/result tables.
        The OP2 header is not read by this function.

        Parameters
        ----------
        table_name : bytes str
            the first table's name

        Returns
        -------
        table_names : List[bytes str]
            the table names that were read

        """
        op2_reader = self.op2_reader
        table_names = []
        self.table_count = defaultdict(int)
        while table_name is not None:
            self.table_count[table_name] += 1
            table_names.append(table_name)

            if self.is_debug_file:
                self.binary_debug.write('-' * 80 + '\n')
                self.binary_debug.write('table_name = %r\n' % (table_name))

            if is_release:
                self.log.debug('  table_name=%r' % table_name)

            self.table_name = table_name
            #if 0:
                #op2_reader._skip_table(table_name)
            #else:
            #print(table_name, table_name in op2_reader.mapped_tables)
            if table_name in self.generalized_tables:
                t0 = self.f.tell()
                self.generalized_tables[table_name](self)
                assert self.f.tell() != t0, 'the position was unchanged...'
            elif table_name in op2_reader.mapped_tables:
                t0 = self.f.tell()
                op2_reader.mapped_tables[table_name]()
                assert self.f.tell() != t0, 'the position was unchanged...'
            elif table_name in GEOM_TABLES:
                op2_reader.read_geom_table()  # DIT (agard)
            elif table_name in MATRIX_TABLES:
                op2_reader.read_matrix(table_name)
            elif table_name in RESULT_TABLES:
                op2_reader.read_results_table()
            elif self.skip_undefined_matrices:
                op2_reader.read_matrix(table_name)
            elif table_name.strip() in self.additional_matrices:
                op2_reader.read_matrix(table_name)
            else:
                msg = (
                    'Invalid Table = %r\n\n'
                    'If you have matrices that you want to read, see:\n'
                    '  model.set_additional_matrices_to_read(matrices)'
                    '  matrices = {\n'
                    "      b'BHH' : True,\n"
                    "      b'KHH' : False,\n"
                    '  }  # you want to read some matrices, but not others\n'
                    "  matrices = [b'BHH', b'KHH']  # assumes True\n\n"

                    'If you the table is a geom/result table, see:\n'
                    '  model.set_additional_result_tables_to_read(methods_dict)\n'
                    "  methods_dict = {\n"
                    "      b'OUGV1' : [method3, method4],\n"
                    "      b'GEOM4SX' : [method3, method4],\n"
                    "      b'OES1X1' : False,\n"
                    '  }\n\n'

                    'If you want to take control of the OP2 reader (mainly useful '
                    'for obscure tables), see:\n'
                    "  methods_dict = {\n"
                    "      b'OUGV1' : [method],\n"
                    '  }\n'
                    '  model.set_additional_generalized_tables_to_read(methods_dict)\n' % (
                        table_name)
                )
                raise NotImplementedError(msg)

            table_name = op2_reader._read_table_name(rewind=True, stop_on_failure=False)
        return table_names

    def set_additional_generalized_tables_to_read(self, tables):
        """
        Adds methods to call a generalized table.
        Everything is left to the user.

        ::

          def read_some_table(self):
              # read the data from self.f
              pass

          # let's overwrite the existing OP2 table
          model2 = OP2Geom(debug=True)
          generalized_tables = {
              b'GEOM1S' : read_some_table,
          }

          model.set_additional_generalized_tables_to_read(generalized_tables)

        """
        self._update_generalized_tables(tables)
        self.generalized_tables = tables

    def set_additional_result_tables_to_read(self, tables):
        """
        Adds methods to read additional result tables.
        This is expected to really only be used for skipping
        unsupported tables or disabling enabled tables that are
        buggy (e.g., OUGV1).

        Parameters
        ----------
        tables : Dict[bytes] = varies
            a dictionary of key=name, value=list[method3, method4]/False,
            False : skips a table
                applies self._table_passer to method3 and method4
            method3 : function
                function to read table 3 results (e.g., metadata)
            method4 : function
                function to read table 4 results (e.g., the actual results)

        """
        self._update_generalized_tables(tables)
        table_mapper = self._get_table_mapper()
        #is_added = False
        def func():
            """overloaded version of _get_table_mapper"""
            #if is_added:
                #return table_mapper
            for _key, methods in tables.items():
                if methods is False:
                    table_mapper[_key] = [self._table_passer, self._table_passer]
                else:
                    assert len(methods) == 2, methods
                    table_mapper[_key] = methods
            #is_added = True
            return table_mapper
        self._get_table_mapper = func

    def _update_generalized_tables(self, tables):
        """
        helper function for:
         - set_additional_generalized_tables_to_read
         - set_additional_result_tables_to_read

        """
        global NX_RESULT_TABLES
        global MSC_RESULT_TABLES
        global RESULT_TABLES
        failed_keys = []
        keys = list(tables.keys())
        for _key in keys:
            if not isinstance(_key, bytes):
                failed_keys.append(_key)
            if hasattr(self, 'is_nx') and self.is_nx:
                NX_RESULT_TABLES.append(_key)
            else:
                MSC_RESULT_TABLES.append(_key)
        if failed_keys:
            failed_keys_str = [str(_key) for _key in failed_keys]
            raise TypeError('[%s] must be bytes' % ', '. join(failed_keys_str))
        RESULT_TABLES = NX_RESULT_TABLES + MSC_RESULT_TABLES

        #RESULT_TABLES.sort()
        #assert 'OESXRMS1' in RESULT_TABLES, RESULT_TABLES

    def set_additional_matrices_to_read(self, matrices: Union[List[str], Dict[str, bool]]):
        """
        Matrices (e.g., KHH) can be sparse or dense.

        Parameters
        ----------
        matrices : List[str]; Dict[str] = bool
            List[str]:
                simplified method to add matrices; value will be True
            Dict[str] = bool:
                a dictionary of key=name, value=True/False,
                where True/False indicates the matrix should be read

        .. note:: If you use an already defined table (e.g. KHH), it
                  will be ignored.  If the table you requested doesn't
                  exist, there will be no effect.
        .. note:: Do not use this for result tables like OUGV1, which
                  store results like displacement.  Those are not matrices.
                  Matrices are things like DMIGs.

        """
        if isinstance(matrices, list):
            matrices2 = {}
            for matrix in matrices:
                assert isinstance(matrix, str), 'matrix=%r' % str(matrix)
                matrices2[matrix] = True
            matrices = matrices2

        self.additional_matrices = matrices
        self.additional_matrices = {}
        for matrix_name, matrix in matrices.items():
            if isinstance(matrix_name, bytes):
                self.additional_matrices[matrix_name] = matrix
            else:
                self.additional_matrices[matrix_name.encode('latin1')] = matrix

    def _finish(self):
        """
        Clears out the data members contained within the self.words variable.
        This prevents mixups when working on the next table, but otherwise
        has no effect.

        """
        for word in self.words:
            if word != '???' and hasattr(self, word):
                if word not in ['Title', 'reference_point']:
                    delattr(self, word)
        self.obj = None
        if hasattr(self, 'subtable_name'):
            del self.subtable_name


def main():  # pragma: no cover
    """testing pickling"""
    from pickle import dump, load
    txt_filename = 'solid_shell_bar.txt'
    pickle_file = open(txt_filename, 'wb')
    op2_filename = 'solid_shell_bar.op2'
    op2 = OP2_Scalar()
    op2.read_op2(op2_filename)
    print(op2.displacements[1])
    dump(op2, pickle_file)
    pickle_file.close()

    pickle_file = open(txt_filename, 'r')
    op2 = load(pickle_file)
    pickle_file.close()
    print(op2.displacements[1])


    #import sys
    #op2_filename = sys.argv[1]

    #o = OP2_Scalar()
    #o.read_op2(op2_filename)
    #(model, ext) = os.path.splitext(op2_filename)
    #f06_outname = model + '.test_op2.f06'
    #o.write_f06(f06_outname)

def create_binary_debug(op2_filename: str, debug_file: str, log) -> Tuple[bool, Any]:
    """helper method"""
    binary_debug = None

    if debug_file is not None:
        #: an ASCII version of the op2 (creates lots of output)
        log.debug('debug_file = %s' % debug_file)
        binary_debug = open(debug_file, 'w')
        binary_debug.write(op2_filename + '\n')
        is_debug_file = True
    else:
        is_debug_file = False
    return is_debug_file, binary_debug


if __name__ == '__main__':  # pragma: no cover
    main()
