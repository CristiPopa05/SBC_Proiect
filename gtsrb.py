"""Read labels and preview images from the local GTSRB archive."""

import base64
import csv
import pickle
from pathlib import Path
from zipfile import ZipFile

import cv2
import numpy as np


ARCHIVE = (
    Path(__file__).resolve().parent / "raw_data" / "german-traffic-sign-dataset"
    / "german-traffic-sign-dataset.zip"
)
LABELS = (
    "Limită 20 km/h",
    "Limită 30 km/h",
    "Limită 50 km/h",
    "Limită 60 km/h",
    "Limită 70 km/h",
    "Limită 80 km/h",
    "Sfârșitul limitei de 80 km/h",
    "Limită 100 km/h",
    "Limită 120 km/h",
    "Depășirea interzisă",
    "Depășirea interzisă camioanelor de peste 3,5 t",
    "Intersecție cu un drum fără prioritate",
    "Drum cu prioritate",
    "Cedează trecerea",
    "STOP",
    "Circulația interzisă în ambele sensuri",
    "Accesul interzis camioanelor de peste 3,5 t",
    "Accesul interzis",
    "Atenție",
    "Curbă periculoasă la stânga",
    "Curbă periculoasă la dreapta",
    "Curbă dublă",
    "Drum cu denivelări",
    "Drum alunecos",
    "Drum îngustat pe dreapta",
    "Lucrări",
    "Semafoare înainte",
    "Atenție, pietoni",
    "Copii",
    "Atenție, bicicliști",
    "Atenție, gheață sau zăpadă",
    "Animale sălbatice",
    "Sfârșitul limitărilor de viteză și al interdicțiilor de depășire",
    "Obligatoriu la dreapta",
    "Obligatoriu la stânga",
    "Obligatoriu înainte",
    "Înainte sau la dreapta",
    "Înainte sau la stânga",
    "Ocolire prin dreapta",
    "Ocolire prin stânga",
    "Sens giratoriu",
    "Sfârșitul interdicției de depășire",
    "Sfârșitul interdicției de depășire pentru camioane",
)
CAMERA_CLASSES = {
    0: "Speed Limit 20",
    1: "Speed Limit 30",
    2: "Speed Limit 50",
    3: "Speed Limit 60",
    4: "Speed Limit 70",
    5: "Speed Limit 80",
    7: "Speed Limit 100",
    8: "Speed Limit 120",
    9: "No Overtaking",
    12: "Priority road",
    13: "Yield",
    14: "Stop",
    17: "No Entry",
    18: "Warning",
    40: "Roundabout",
}


class NumpyArrays(pickle.Unpickler):
    def find_class(self, module, name):
        if module == "numpy" and name in {"ndarray", "dtype"}:
            return super().find_class(module, name)
        if module == "numpy.core.multiarray" and name == "_reconstruct":
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"Unexpected object in GTSRB archive: {module}.{name}")


def read_samples(archive, filename):
    if archive.getinfo(filename).file_size > 150_000_000:
        raise ValueError(f"Unexpected size for {filename}.")
    with archive.open(filename) as source:
        samples = NumpyArrays(source).load()
    if not isinstance(samples, dict):
        raise ValueError(f"Unexpected GTSRB data in {filename}.")
    frames, classes = samples["features"], samples["labels"]
    if (
        not isinstance(frames, np.ndarray) or not isinstance(classes, np.ndarray)
        or frames.dtype != np.uint8 or frames.shape[1:] != (32, 32, 3)
        or classes.dtype != np.uint8 or classes.shape != (len(frames),)
        or set(classes) != set(range(len(LABELS)))
    ):
        raise ValueError(f"Unexpected GTSRB images or labels in {filename}.")
    return frames, classes


def preview_image(frames):
    def sharpness(frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        return cv2.Laplacian(gray, cv2.CV_64F).var()

    frame = cv2.cvtColor(max(frames, key=sharpness), cv2.COLOR_RGB2BGR)
    frame = cv2.resize(frame, (96, 96), interpolation=cv2.INTER_CUBIC)
    ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 86])
    if not ok:
        raise ValueError("Could not encode the GTSRB preview.")
    return "data:image/jpeg;base64," + base64.b64encode(encoded).decode("ascii")


def read_class_names(archive):
    metadata = archive.read("signname.csv").decode("utf-8-sig")
    names = {int(row["ClassId"]): row["SignName"] for row in csv.DictReader(metadata.splitlines())}
    if sorted(names) != list(range(len(LABELS))):
        raise ValueError("Unexpected classes in GTSRB signname.csv.")
    return names


def read_previews(path=ARCHIVE):
    if not path.is_file():
        return {}
    with ZipFile(path) as archive:
        names = read_class_names(archive)
        frames, classes = read_samples(archive, "valid.p")
    return {index: preview_image(frames[classes == index]) for index in names}
