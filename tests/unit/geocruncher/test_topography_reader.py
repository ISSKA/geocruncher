import numpy as np
import pytest

from geocruncher.topography_reader import ascii_grid_to_implicit_dtm


def test_ascii_grid_to_implicit_dtm_reads_valid_grid_with_nodata_header():
    dem = "\n".join(
        [
            "ncols 2",
            "nrows 2",
            "xllcorner 10",
            "yllcorner -20",
            "cellsize 5",
            "NODATA_value -9999",
            "1 2",
            "3 4",
        ]
    )

    dtm = ascii_grid_to_implicit_dtm(dem)

    np.testing.assert_allclose(dtm.origin, np.array([10, -20], dtype=float))
    np.testing.assert_allclose(dtm.steps, np.array([5, 5], dtype=float))
    np.testing.assert_allclose(dtm.z, np.array([[3, 1], [4, 2]], dtype=float))


def test_ascii_grid_to_implicit_dtm_reads_valid_grid_with_dx_dy_header():
    dem = "\n".join(
        [
            "ncols 2",
            "nrows 2",
            "xllcorner 10",
            "yllcorner -20",
            "dx 5",
            "dy 5",
            "NODATA_value -9999",
            "1 2",
            "3 4",
        ]
    )

    dtm = ascii_grid_to_implicit_dtm(dem)

    np.testing.assert_allclose(dtm.origin, np.array([10, -20], dtype=float))
    np.testing.assert_allclose(dtm.steps, np.array([5, 5], dtype=float))
    np.testing.assert_allclose(dtm.z, np.array([[3, 1], [4, 2]], dtype=float))


def test_ascii_grid_to_implicit_dtm_reads_grid_without_optional_nodata_header():
    dem = "\n".join(
        [
            "ncols 2",
            "nrows 2",
            "xllcorner 10",
            "yllcorner -20",
            "cellsize 5",
            "1 2",
            "3 4",
        ]
    )

    dtm = ascii_grid_to_implicit_dtm(dem)

    np.testing.assert_allclose(dtm.z, np.array([[3, 1], [4, 2]], dtype=float))


def test_ascii_grid_to_implicit_dtm_rejects_malformed_header_values():
    dem = "\n".join(
        [
            "ncols 2",
            "nrows 2",
            "xllcorner nope",
            "yllcorner -20",
            "cellsize 5",
            "NODATA_value -9999",
            "1 2",
            "3 4",
        ]
    )

    with pytest.raises(
        ValueError, match="Invalid value for header 'xllcorner': 'nope' in DEM"
    ):
        ascii_grid_to_implicit_dtm(dem)


def test_ascii_grid_to_implicit_dtm_rejects_grid_with_missing_required_headers():
    dem = "\n".join(
        [
            "ncols 2",
            "nrows 2",
            "xllcorner 10",
            "NODATA_value -9999",
            "1 2",
            "3 4",
        ]
    )

    with pytest.raises(ValueError, match="Missing required header: yllcorner in DEM"):
        ascii_grid_to_implicit_dtm(dem)


def test_ascii_grid_to_implicit_dtm_rejects_grid_without_resolution():
    dem = "\n".join(
        [
            "ncols 2",
            "nrows 2",
            "xllcorner 10",
            "yllcorner -20",
            "NODATA_value -9999",
            "1 2",
            "3 4",
        ]
    )

    with pytest.raises(ValueError, match="Missing cellsize or dx/dy header in DEM."):
        ascii_grid_to_implicit_dtm(dem)
