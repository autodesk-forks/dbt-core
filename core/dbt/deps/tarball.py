import os
from pathlib import Path

from dbt.clients import system
from dbt.config.project import PartialProject
from dbt.contracts.project import TarballPackage
from dbt.deps.base import PinnedPackage, UnpinnedPackage, get_downloads_path
from dbt.exceptions import DependencyError


class TarballPackageMixin:
    def __init__(self, tarball: str) -> None:
        super().__init__()
        self.tarball = tarball

    @property
    def name(self):
        return self.tarball

    def source_type(self) -> str:
        return "tarball"


class TarballPinnedPackage(TarballPackageMixin, PinnedPackage):
    def __init__(self, tarball: str, package: str) -> None:
        super().__init__(tarball)
        self.package = package
        self.version = "tarball"
        self.tar_path = os.path.join(Path(get_downloads_path()), self.package)
        self.untarred_path = f"{self.tar_path}_untarred"

    @property
    def name(self):
        return self.package

    def get_version(self):
        return self.version

    def nice_version_name(self):
        return f"tarball (url: {self.tarball})"

    def _fetch_metadata(self, project, renderer):
        """Download and untar the project and parse metadata from the project folder."""
        system.download(self.tarball, self.tar_path)
        system.untar_package(self.tar_path,self.untarred_path)
        tar_contents = os.listdir(self.untarred_path)
        if len(tar_contents) != 1:
            raise DependencyError(
                f"Incorrect structure for package extracted from {self.tarball}."
                f"The extracted package needs to follow the structure {self.name}/<package_contents>."
            )
        child_folder = os.listdir(self.untarred_path)[0]

        self.untarred_path = os.path.join(self.untarred_path,child_folder)
        partial = PartialProject.from_project_root(self.untarred_path)
        metadata = partial.render_package_metadata(renderer)
        metadata.name = self.package if self.package else metadata.name
        return metadata

    def install(self, project, renderer):
        dest_path = self.get_installation_path(project, renderer)
        if os.path.exists(dest_path):
            if system.path_is_symlink(dest_path):
                system.remove_file(dest_path)
            else:
                system.rmdir(dest_path)
        system.move(self.untarred_path, dest_path)


class TarballUnpinnedPackage(TarballPackageMixin, UnpinnedPackage[TarballPinnedPackage]):
    def __init__(
        self,
        tarball: str,
        package: str,
    ) -> None:
        super().__init__(tarball)
        # setup to recycle RegistryPinnedPackage fns
        self.package = package
        self.version = "tarball"

    @classmethod
    def from_contract(cls, contract: TarballPackage) -> "TarballUnpinnedPackage":
        return cls(tarball=contract.tarball, package=contract.name)

    def incorporate(self, other: "TarballUnpinnedPackage") -> "TarballUnpinnedPackage":
        return TarballUnpinnedPackage(tarball=self.tarball, package=self.package)

    def resolved(self) -> TarballPinnedPackage:
        return TarballPinnedPackage(tarball=self.tarball, package=self.package)
