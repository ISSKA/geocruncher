from typing import NamedTuple


class VkProfilerSettings(NamedTuple):
    # version of the profiler
    version: int
    # name of the type of computation
    computation: str
    # list of names of the steps to record
    steps: list[str]
    # additional metadata for this computation
    metadata: list[str]


class MetadataHelpers:
    """Static functions that help gather metadata for the profiling"""
    @staticmethod
    def num_series(model) -> int:
        return len(model.pile.all_series)

    @staticmethod
    def num_units(model) -> int:
        # remove 1 from nbformations because it always includes the dummy
        return model.nbformations() - 1

    @staticmethod
    def num_finite_faults(model) -> int:
        return len([x for name, x in model.faults_data.items() if not x.infinite])

    @staticmethod
    def num_infinite_faults(model) -> int:
        return len([x for name, x in model.faults_data.items() if x.infinite])

    @staticmethod
    def num_interfaces(model, unit=True, fault=True) -> int:
        num_unit_interfaces = 0
        num_fault_interfaces = 0
        if unit:
            # divide interfaces by 2, because they are lines made of 2 points
            num_unit_interfaces = len(
                [a for s in model.pile.all_series if s.potential_data is not None for i in s.potential_data.interfaces for a in i]) / 2
        if fault:
            num_fault_interfaces = len(
                [a for f in model.faults_data.values() if f.potential_data is not None for i in f.potential_data.interfaces for a in i]) / 2

        return num_unit_interfaces + num_fault_interfaces

    @staticmethod
    def num_foliations(model, unit=True, fault=True) -> int:
        num_unit_foliations = 0
        num_fault_foliations = 0
        if unit:
            # divide interfaces by 2, because they are lines made of 2 points
            num_unit_foliations = len([
                l for s in model.pile.all_series if s.potential_data is not None for l in s.potential_data.gradients.locations])
        if fault:
            num_fault_foliations = len([
                l for f in model.faults_data.values() if f.potential_data is not None for l in f.potential_data.gradients.locations])

        return num_unit_foliations + num_fault_foliations
