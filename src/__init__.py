import importlib.metadata

from .app import SnipasteApp as SnipasteApp

try:
    __version__ = importlib.metadata.version("openSnipaste")
except importlib.metadata.PackageNotFoundError:
    __version__ = "1.2.0"
