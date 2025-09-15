import logging

from pykarstnsim.karstnsim import run_simulation
from pykarstnsim.models import ConnectivityMatrix, ProjectBox, Sink, Spring, Surface

logging.basicConfig(level=logging.INFO)

from pathlib import Path

from pykarstnsim.config import KarstConfig

LOGGER = logging.getLogger(__name__)
# Instantiate config
CONFIG = KarstConfig()

# disable deadend points for demo
CONFIG.nb_deadend_points = 0

project_box = ProjectBox.from_file(CONFIG.domain)
sinks = Sink.from_file(CONFIG.sinks)
springs = Spring.from_file(CONFIG.springs)
connectivity_matrix = ConnectivityMatrix.from_file(CONFIG.connectivity_matrix)
water_tables = [Surface.from_file(Path(p)) for p in CONFIG.surf_wat_table]
topo_surface = Surface.from_file(CONFIG.topo_surface)
inception_surfaces = [Surface.from_file(p) for p in CONFIG.inception_surfaces]

res = run_simulation(
    CONFIG,
    project_box=project_box,
    sinks=sinks,
    springs=springs,
    connectivity_matrix=connectivity_matrix,
    water_tables=water_tables,
    topo_surface=topo_surface,
    inception_surfaces=inception_surfaces,
)

if res is None:
    LOGGER.error("Simulation failed, no result returned.")
    exit(1)

print("Simulation result:", res)

Path("sample_output.txt").write_text(res.to_string())
