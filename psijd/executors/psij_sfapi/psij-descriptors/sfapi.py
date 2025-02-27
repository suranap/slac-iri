from packaging.version import Version

from psij.descriptor import Descriptor

__PSI_J_EXECUTORS__ = [Descriptor(name='sfapi', version=Version('0.0.1'),
                                   cls='psij_sf.psif_sf.SFAPIExecutor')]
