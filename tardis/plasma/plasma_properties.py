from abc import ABCMeta, abstractmethod

from astropy import constants as const
import numpy as np
import pandas as pd

from tardis.plasma.exceptions import IncompleteAtomicData



class BasePlasmaProperty(object):
    __metaclass__ = ABCMeta

    def __init__(self, plasma_parent):
        self.plasma_parent = plasma_parent

    def update(self):
        args = [getattr(self.plasma_parent, item) for item in self.inputs]
        self.value = self.calculate(*args)

    @abstractmethod
    def calculate(self, *args, **kwargs):
        raise NotImplementedError('This method needs to be implemented by ')

    def get_label(self):
        return "Name: {0}\nType: {1}\n{2}".format(self.name, self.type_str,
                                                  getattr(self,
                                                          'latex_str', ''))


class BaseAtomicDataProperty(BasePlasmaProperty):
    inputs = ['atomic_data']
    def __init__(self, plasma_parent):
        super(BaseAtomicDataProperty, self).__init__(plasma_parent)
        self.value = None

    def calculate(self, atomic_data):
        if self.value is not None:
            return self.value
        else:
            if not getattr(atomic_data, 'has_{0}'.format(
                    self.name)):
                raise IncompleteAtomicData(self.name)
            else:
                self.value = getattr(atomic_data, self.name)



class AtomicLevels(BaseAtomicDataProperty):
    name = 'levels'
    type_str = 'pandas.DataFrame'

class AtomicLines(BaseAtomicDataProperty):
    name = 'lines'
    type_str = 'pandas.DataFrame'



class BetaRadiation(BasePlasmaProperty):

    name = 'beta_rad'
    inputs = ['t_rad']
    type_str = 'numpy.array'
    latex_str = '$\\frac{1}{K_B T_\\textrm{rad}}$'

    def __init__(self, plasma_parent):
        super(BetaRadiation, self).__init__(plasma_parent)
        self.k_B_cgs = const.k_B.cgs.value


    def calculate(self, t_rad):
        return (1 / (self.k_B_cgs * t_rad))

class LevelBoltzmannFactor(BasePlasmaProperty):
    """
    Calculate the level population Boltzmann factor
    """

    name = 'level_boltzmann_factor'
    inputs = ['levels', 'beta_rad']
    label = 'test'

    def calculate(self, levels, beta_rad):
        exponential = np.exp(np.outer(levels.energy.values, -beta_rad))
        level_boltzmann_factor_array = (levels.g.values[np.newaxis].T *
                                        exponential)

        level_boltzmann_factor = pd.DataFrame(level_boltzmann_factor_array,
                                              index=levels.index,
                                              columns=np.arange(len(beta_rad)),
                                              dtype=np.float64)
        return level_boltzmann_factor

class PartitionFunction(BasePlasmaProperty):
    """
    Calculate partition functions for the ions using the following formula, where
    :math:`i` is the atomic_number, :math:`j` is the ion_number and :math:`k` is the level number.

    .. math::
        Z_{i,j} = \\sum_{k=0}^{max(k)_{i,j}} g_k \\times e^{-E_k / (k_\\textrm{b} T)}



    if self.initialize is True set the first time the partition functions are initialized.
    This will set a self.partition_functions and initialize with LTE conditions.


    Returns
    -------

    partition_functions : `~astropy.table.Table`
        with fields atomic_number, ion_number, partition_function

    """

    inputs = ['levels', 'level_boltzmann_factor']
    label = 'test'

    def calculate(self, levels, level_boltzmann_factor):

        level_population_proportional_array = levels.g.values[np.newaxis].T *\
                                              np.exp(np.outer(levels.energy.values, -self.beta_rads))
        level_population_proportionalities = pd.DataFrame(level_population_proportional_array,
                                                               index=self.atom_data.levels.index,
                                                               columns=np.arange(len(self.t_rads)), dtype=np.float64)


        #level_props = self.level_population_proportionalities

        partition_functions = level_population_proportionalities[self.atom_data.levels.metastable].groupby(
            level=['atomic_number', 'ion_number']).sum()
        partition_functions_non_meta = self.ws * level_population_proportionalities[~self.atom_data.levels.metastable].groupby(
            level=['atomic_number', 'ion_number']).sum()
        partition_functions.ix[partition_functions_non_meta.index] += partition_functions_non_meta
        if self.nlte_config is not None and self.nlte_config.species != [] and not initialize_nlte:
            for species in self.nlte_config.species:
                partition_functions.ix[species] = self.atom_data.levels.g.ix[species].ix[0] * \
                                                       (self.level_populations.ix[species] /
                                                        self.level_populations.ix[species].ix[0]).sum()

        return level_population_proportionalities, partition_functions

