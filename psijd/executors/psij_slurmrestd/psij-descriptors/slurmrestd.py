from packaging.version import Version

from psij.descriptor import Descriptor

__PSI_J_EXECUTORS__ = [Descriptor(name='slurmrestd', version=Version('0.0.1'),
                                   cls='psij_slurmrestd.slurmrestd.SlurmRestAPIExecutor')]
