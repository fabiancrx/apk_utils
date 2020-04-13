import json
import logging
from io import BytesIO
from pathlib import Path
from typing import List, Callable, Dict, Tuple, Any

from PIL import Image
from pyaxmlparser import APK
from pyaxmlparser.core import BrokenAPKError

from decorators import timeit

log = logging.getLogger("apk_utils.core")

# TODO figure out how to manage/encapsulate this global state (classes, HOF's)
# first add more features then
# maybe improve performance caching the dict into a json and confirming identity via md5 fo already processed apk's


# ray Type aliases make more clearer the intent of the data structures used.
# Although this annotation doesn't enforce errors at compile time

AppPackage = str
version_code = int
app_name = str
version_name = str

# Base structures besides of APK itself used in the script

ApkMetadata = Tuple[version_code, Path, app_name, version_name]

# Dict[str, List[Tuple[int, Path, str, str]]]
ApkLibrary = Dict[AppPackage, List[ApkMetadata]]

BASE_DIR: str
CACHE_FILE: str


# class Repository:
#     BASE_DIR: str
#     CACHE_FILE: str
#
#     def __init__(self, path: str):
#         self.BASE_DIR = path
#         self.CACHE_FILE=self.BASE_DIR + '/cache.json'

# ray function with type annotation in the parameters and in the response.
def files_by_extension(directory: str, extension: str, recursive: bool = False, ) -> List[Path]:
    """
    Takes a directory and an extension as input and returns a List of the Paths
    of all the files matching the supplied extension.
    If recursive is True subdirectories will be traversed.
    """
    directory_path = valid_path(directory)
    iterate_pattern = f'**/*{extension}' if recursive else f'*{extension}'
    return [entry for entry in directory_path.glob(iterate_pattern) if entry.is_file()]


def valid_path(directory: str) -> Path:
    directory_path = Path(directory)
    if not directory_path.exists() or not directory_path.is_dir():
        log.warning(f"'{directory}' is not a valid directory or it does not exists")
        raise Exception(f"'{directory}' is not a valid directory or it does not exists")
    return directory_path


def formatted_apk_name(apk: APK) -> str: return f'{apk.get_app_name()}_v{apk.version_code}.apk'


def formatted_apk_name_from_meta(meta: ApkMetadata) -> str: return f'{meta[2]}_v{meta[0]}.apk'


def apk_applier(list_apk: List[Path], function: Callable[[APK], Any], ):
    """Higher order function that applies the `callable` function to every element of `list_apk`"""
    local_dict = {}
    for apk_path in list_apk:
        try:
            apk = APK(str(apk_path), raw=False)
            log.info(f"Applying function {function} to {apk.filename}")
            local_dict[apk_path.name] = function(apk)
        except BrokenAPKError as e:
            log.warning(f"{apk_path} is not a valid APK , skipping file because of {e.__cause__}")
            continue
    with open(Path(BASE_DIR + '/cache.json'), 'w')as output:
        output.write(json.dumps(local_dict))


def extract_icon_io(apk: APK, max_dpi=640) -> str:
    """Extracts an apk image to the filesystem
    and creates a naive cache of images for optimization of incremental runs"""

    try:
        apk_name = apk.get_app_name()
        image_name = f"{apk_name}.png"
        image_path = Path(BASE_DIR, 'app_icon', )
        image_path.mkdir(parents=True, exist_ok=True)
        image = apk.get_file(apk.get_app_icon(max_dpi=max_dpi))

        pillow_image = Image.open(BytesIO(image))
        pillow_image.verify()

    except Exception as e:
        log.error(f"IMAGE IS NOT VALID {apk.filename} \n {e.__cause__}")
        return apk.filename
    try:
        with open(Path(image_path, image_name), 'wb')as output:
            log.info('writing image to ' + str(image_path))
            output.write(image)
    except Exception as e:
        log.warning(f'could not save image for {image_name}')
        log.error(e)
    return image_name


def get_meta_from_apk(apk: APK) -> ApkMetadata:
    return int(apk.version_code), Path(apk.filename), apk.get_app_name(), apk.version_name


@timeit
def get_library(list_apk: List[Path]) -> ApkLibrary:
    if not list_apk:
        print('No apk files found ')
        return {}
    library = {}
    total = len(list_apk)
    counter = 0
    for apk_path in list_apk:
        apk = APK(str(apk_path))
        try:
            meta = get_meta_from_apk(apk)
        except Exception as e:
            log.error(e)
            continue
        if apk.package not in library:
            library[apk.package] = [meta]
        else:
            library[apk.package].append(meta)
        counter += 1
        print(f'{counter / total * 100}%')
    return library


# ray this is a decorator it wraps the  function underneath it and runs it. In this case I use it for
# performace/time testing but in other cases can be used to cache results see'lru_cache' in zeal or require
# authentication to access a resource in a web server like django
# you are free to toy around whit timeit in decorators.py
@timeit
def renamer(apk_lib: ApkLibrary, delete_duplicates=False, delete_old_versions=False) -> None:
    # Dict[str, List[Tuple[int, Path, str(app_name), str(app_version)]]]
    dupe_counter = 0
    old_counter = 0
    for app in apk_lib:
        # ray list comprehension applies a function to elements and returns a list
        # ray here is used to get only the version code of the tuple
        versions = [item[0] for item in apk_lib[app]]
        max_version = max(versions)
        local_dupes = 0
        for metadata in apk_lib[app]:
            # ray tuple unpacking unwraps a tuple of N items in N variables
            (version_code, path, name, version_name) = metadata

            suffix = '' if version_code == max_version else '.old'
            new_name = formatted_apk_name_from_meta(metadata)
            new_path = Path(path.parent, new_name + suffix)

            if new_path == path:
                continue
            elif new_path.exists():
                suffix = f'[{local_dupes}].dupe'  # duplicate
                local_dupes += 1
                dupe_counter += 1
                if delete_duplicates:
                    path.unlink()
                    continue
                new_path = Path(path.parent, new_name + suffix)

            elif suffix == '.old':
                old_counter += 1
                if delete_old_versions:
                    path.unlink()
                    continue
            try:
                path.rename(new_path)
            except Exception as e:
                print(f'error with {new_path}')
                log.error(e)
    print(f"Old versions => {old_counter}\nDuplicate versions => {dupe_counter} ")


if __name__ == '__main__':
    # the folder variable should have apk files inside it
    BASE_DIR = "/run/media/croxx/System/3uTools/apks/APK's/"
    list_of_paths_to_apks = files_by_extension(BASE_DIR, '.apk')
    # use case 1: rename and organize apks marking old and duplicates
    # lib = get_library(list_of_paths_to_apks)
    # renamer(lib)
    # use case 2: extract images
    list_of_paths_to_apks = files_by_extension(BASE_DIR, '.apk')
    # ray notice how the second parameter is a function but without calling it with the parenthesis at the end
    # eg: extract_image_io() this way im passing a reference to the function
    # and my apk applier calls this function for each apk. This way if another function that operates independently on
    # each apk say "names_to_csv" or "get_resources" just need to be coded the specific logic for them
    # and apk applier takes care of the iteration and error handling of paths and extracting apk's

    apk_applier(list_of_paths_to_apks, extract_icon_io)

    # A function that takes other functions as parameters or returns functions is called a higher order function.
    # in this case I take advantage of this in apk_applier to avoid future code duplication as I explained above.
