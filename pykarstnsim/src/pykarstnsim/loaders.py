import logging
from pathlib import Path
import pykarstnsim_core

LOGGER = logging.getLogger(__name__)

def _open_lines(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Missing input file: {path}")
    return [ln.rstrip("\n") for ln in path.read_text(encoding="utf-8", errors="ignore").splitlines() if ln.strip()]

def load_box_with_properties(path: Path) -> tuple[pykarstnsim_core.Box, list[list[float]]]:
    """Parse box file and return (Box, properties list).

    Mirrors C++ load_box in read_files.cpp to also capture cell properties.
    Properties lines: idx p0 p1 ...; property count given on second line after header.
    """
    raw = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if len(raw) < 10:
        raise ValueError(f"Box file too short: {path}")
    # header line raw[0]
    second = raw[1].split()
    if len(second) < 2:
        raise ValueError(f"Malformed second line in box file: {raw[1]}")
    # property count may not be strictly int convertible (permissive)
    try:
        prop_size = int(second[1])
    except Exception:
        prop_size = 0
    def _vec(line: str) -> pykarstnsim_core.Vector3:
        parts = line.split()
        if len(parts) < 4:
            raise ValueError(f"Malformed vector line in box file {path}: {line}")
        return pykarstnsim_core.Vector3(float(parts[1]), float(parts[2]), float(parts[3]))
    basis = _vec(raw[2])
    u = _vec(raw[3])
    v = _vec(raw[4])
    w = _vec(raw[5])
    nu = int(raw[6].split()[1])
    nv = int(raw[7].split()[1])
    nw = int(raw[8].split()[1])
    box = pykarstnsim_core.Box(basis, u, v, w, nu, nv, nw)
    # properties start after header line raw[9]
    props: list[list[float]] = []
    for line in raw[10:]:
        parts = line.split()
        if not parts:
            continue
        # Expect idx then prop_size floats (if any)
        if len(parts) >= 1 + prop_size:
            try:
                int(parts[0])
                values = []
                for tok in parts[1:1+prop_size]:
                    try:
                        values.append(float(tok))
                    except ValueError:
                        values.append(float('nan'))
                if values:
                    props.append(values)
            except ValueError:
                continue
    return box, props

def load_box(path: Path) -> pykarstnsim_core.Box:  # backwards compat for existing calls
    return load_box_with_properties(path)[0]

def load_surface(path: Path) -> pykarstnsim_core.Surface:
    """Parse GOCAD-like surface file with VRTX / TRGL tags."""
    lines = _open_lines(path)
    if len(lines) < 3:
        return pykarstnsim_core.Surface()
    # First pass: just iterate after header (skip first line)
    pts: list[pykarstnsim_core.Vector3] = []
    tris: list[pykarstnsim_core.Triangle] = []
    for ln in lines[1:]:
        parts = ln.split()
        if not parts:
            continue
        tag = parts[0]
        if tag == "VRTX" and len(parts) >= 5:
            # VRTX idx x y z [props...]
            x, y, z = map(float, parts[2:5]) if parts[1].isdigit() else map(float, parts[1:4])
            # handle uncertain position of idx; robust fallback
            if parts[1].isdigit():
                x, y, z = map(float, parts[2:5])
            else:
                x, y, z = map(float, parts[1:4])
            pts.append(pykarstnsim_core.Vector3(x, y, z))
        elif tag == "TRGL" and len(parts) >= 5:
            # TRGL idx a b c (C++ ignores idx, keeps a b c)
            # Some files might be: TRGL a b c (no leading idx)
            if parts[1].isdigit() and parts[2].isdigit() and parts[3].isdigit() and parts[4].isdigit():
                a, b, c = map(int, parts[2:5])
            else:
                # assume form TRGL a b c
                a, b, c = map(int, parts[1:4])
            tris.append(pykarstnsim_core.Triangle(a, b, c))
    return pykarstnsim_core.Surface(pts, tris, path.stem)

def load_pointset_with_properties(path: Path) -> tuple[list[pykarstnsim_core.Vector3], list[list[float]]]:
    """Parse point set file capturing per-point properties.

    Mirrors C++ load_pointset: header line then per line: idx x y z [props...].
    Returns (points, properties list where each item is list[float] of properties)."""
    raw = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if len(raw) < 2:
        return [], []
    # Determine property count from second line token count minus four (idx x y z)
    second_tokens = raw[1].split()
    prop_size = max(len(second_tokens) - 4, 0)
    pts: list[pykarstnsim_core.Vector3] = []
    props: list[list[float]] = []
    # Skip header raw[0]
    any_with_index = False
    any_without_index = False
    for line in raw[1:]:
        parts = line.split()
        if len(parts) < 4:
            continue
        # Accept both indexed and non-indexed lines
        cursor = 0
        try:
            int(parts[0])
            cursor = 1
            any_with_index = True
        except ValueError:
            cursor = 0
            any_without_index = True
        try:
            x = float(parts[cursor]); y = float(parts[cursor+1]); z = float(parts[cursor+2])
        except (ValueError, IndexError):
            continue
        pts.append(pykarstnsim_core.Vector3(x, y, z))
        prop_tokens = parts[cursor+3:]
        values: list[float] = []
        for tok in prop_tokens[:prop_size]:
            try:
                values.append(float(tok))
            except ValueError:
                values.append(float('nan'))
        # pad if fewer tokens read
        if len(values) < prop_size:
            values.extend([float('nan')] * (prop_size - len(values)))
        props.append(values)
    if any_with_index and any_without_index:
        LOGGER.warning(f"Mixed indexed and non-indexed lines in {path}. C++ expects indices; property alignment may differ.")
    elif any_without_index:
        LOGGER.warning(f"No leading indices detected in {path}. C++ parser requires an index; results may differ.")
    return pts, props

def load_points(path: Path) -> list[pykarstnsim_core.Vector3]:  # original simple geometry loader
    return load_pointset_with_properties(path)[0]

def load_line(path: Path) -> pykarstnsim_core.Line:
    """Parse polyline file where each segment is defined by two successive point lines (C++ load_line)."""
    lines = _open_lines(path)
    if len(lines) < 3:
        return pykarstnsim_core.Line()
    # skip header (line 0); token counting on line 1 in C++ is only for prop size; we ignore properties
    data = lines[1:]  # keep potential even number requirement
    # ensure odd header removal similar to C++ (they skip header again after rewind). We'll treat data[1:] as actual points.
    pts_lines = data[1:]
    segs: list[pykarstnsim_core.Segment] = []
    it = iter(pts_lines)
    for first in it:
        try:
            second = next(it)
        except StopIteration:
            break  # unmatched point at end -> ignore
        def _parse_point(line: str) -> pykarstnsim_core.Vector3:
            parts = line.split()
            if len(parts) < 4:
                raise ValueError(f"Malformed line point in {path}: {line}")
            try:
                int(parts[0])
                x, y, z = map(float, parts[1:4])
            except ValueError:
                x, y, z = map(float, parts[0:3])
            return pykarstnsim_core.Vector3(x, y, z)
        p1 = _parse_point(first)
        p2 = _parse_point(second)
        segs.append(pykarstnsim_core.Segment(p1, p2))
    return pykarstnsim_core.Line(segs)

def load_previous_network(path: Path) -> pykarstnsim_core.Line:
    return load_line(path)

def load_distribution(path: Path) -> list[float]:
    """Simple whitespace-separated float loader."""
    if not path.exists():
        return []
    vals: list[float] = []
    for ln in path.read_text(encoding="utf-8", errors="ignore").split():
        try:
            vals.append(float(ln))
        except ValueError:
            continue
    return vals

def load_connectivity_matrix_py(sinks: list[pykarstnsim_core.Vector3], springs: list[pykarstnsim_core.Vector3], matrix_path: Path, pad_value: int = 1) -> list[list[int]]:
    """Python version of C++ KarsticNetwork::read_connectivity_matrix.

    Accepts the full path to the connectivity matrix file (like other loaders).
    Rows = sinks, Cols = springs. Tab separated values per line.

    This function will raise FileNotFoundError if the file does not exist.
    """
    nb_sinks = len(sinks)
    nb_springs = len(springs)
    if nb_sinks == 0 or nb_springs == 0:
        LOGGER.warning("No sinks or springs defined; connectivity matrix will be empty.")
        return []
    if not matrix_path.exists():
        raise FileNotFoundError(f"Missing connectivity matrix file: {matrix_path}")
    data: list[list[int]] = []
    for row_idx, line in enumerate(matrix_path.read_text(encoding="utf-8", errors="ignore").splitlines()):
        if not line.strip():
            continue
        cols = line.rstrip().split("\t")
        row_vals: list[int] = []
        for col_idx, tok in enumerate(cols):
            try:
                row_vals.append(int(tok))
            except ValueError:
                raise ValueError(f"Invalid int at row {row_idx} col {col_idx} in {matrix_path}: '{tok}'") from None
        # Pad / trim to nb_springs for safety
        if len(row_vals) < nb_springs:
            row_vals.extend([pad_value] * (nb_springs - len(row_vals)))
        elif len(row_vals) > nb_springs:
            row_vals = row_vals[:nb_springs]
        data.append(row_vals)
        if len(data) == nb_sinks:
            break
    # Ensure full matrix shape
    while len(data) < nb_sinks:
        data.append([pad_value] * nb_springs)
    return data
