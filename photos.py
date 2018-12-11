'''
Photograph directory structure.
Root
    *.* # Exclude. Random nonsense.
    *export*/ #exclude
    workspace/ #art program project files
    Processed/ #Finished photographs
        jpg/ # Exclude. compressed jpgs. Bound for google photos.
        tiff/
    Camera Roll/
        DD-MM-YYYY/
            *.raw
            *.xmp #darktable sidecar
            jpg/
                *.jpg #out-of-camera jpg. Filename matches raw file name. Cleanup: delete all jpgs without matching raw file.
'''
import logging
import sys

from PIL import Image
from shutil import copyfile
import exifread
import os
import argparse
import datetime

DATE_FILE_FORMAT="%m-%d-%Y"
EXIF_DATE_TOKEN_FORMAT='%Y:%m:%d %H:%M:%S'
JPG_NAME = ['.jpg', '.jpeg']
RAW_NAME = ['.cr2', '.dng']
SIDECAR_NAME = ['.xmp']

logger = logging.getLogger("camera-roll-utils")
logger.addHandler(logging.StreamHandler(sys.stdout))

def doFileTransfer(src, dest, transferCommand):
    if src != dest:
        if not os.path.exists(dest):
            transferCommand(src, dest)
            return True
        else:
            logger.error("ERROR: File already exists. From {} To {}".format(src, dest))
            return False

def doMakeDir(dest, mkdirCommand):
    try:
        mkdirCommand(dest)
        return True
    except os.error:
        logger.error("Error creating directory: {}".format(dest))
        return False

def preProcessInputDir(importPath):
    existingDirectories = []
    unsortedRaw = {}
    sidecars = {}
    unsortedJpg = {}
    for root, subdirs, files in os.walk(os.path.normpath(importPath)):
        if root == importPath:
            for _dir in subdirs:
                try:
                    datetime.datetime.strptime(_dir, DATE_FILE_FORMAT)
                    existingDirectories.append(_dir)
                except:
                    pass
        elif not any(substring in root for substring in existingDirectories):
            print("Skipping directory: {}", root)
            continue

        for _file in files:
            filename, fileExtension = os.path.splitext(_file)
            if fileExtension.lower() in JPG_NAME:
                workingDict = unsortedJpg
            elif fileExtension.lower() in RAW_NAME:
                workingDict = unsortedRaw
            elif fileExtension.lower() in SIDECAR_NAME:
                sidecars[filename] = os.path.join(root, _file)
                continue
            else:
                logger.error("ERROR: Unrecognized file extension: {}".format(os.path.join(root, _file)))
                continue

            imageStrDate = get_date_taken(os.path.join(os.path.join(root, _file)))
            imageDate = datetime.datetime.strptime(imageStrDate, EXIF_DATE_TOKEN_FORMAT)
            key = imageDate.strftime(DATE_FILE_FORMAT)
            if workingDict.get(key) is None:
                workingDict[key] = []
            workingDict[key].append(os.path.join(root, _file))
    return existingDirectories, unsortedRaw, sidecars, unsortedJpg

def importFilesFromCard(directories, transferCommand, mkdirCommand):
    outputSortedFiles(directories[1], preProcessInputDir(directories[0]), transferCommand, mkdirCommand)

def organizeInPlace(cameraRollDirectory, transferCommand, mkdirCommand):
    outputSortedFiles(cameraRollDirectory, preProcessInputDir(cameraRollDirectory), transferCommand, mkdirCommand)

def outputSortedFiles(outputDirectory, preProcessResults, transferCommand, mkdirCommand):
    existingDirectories, unsortedRaw, sidecars, unsortedJpg = preProcessResults

    for _key, _value in unsortedRaw.items():
        _path = os.path.join(outputDirectory, _key)
        if _key not in existingDirectories:
            if not doMakeDir(_path, mkdirCommand):
                sys.exit("Error creating directory: {}".format(_path))

        for _file in _value:
            basename = os.path.basename(_file)
            doFileTransfer(_file, os.path.join(_path, basename), transferCommand)
            if sidecars.get(basename) is not None:
                doFileTransfer(sidecars[basename], os.path.join(_path, os.path.basename(sidecars[basename])), transferCommand)

    for _key, _value in unsortedJpg.items():
        _path = os.path.join(outputDirectory, _key, 'jpg')
        if not os.path.exists(_path):
            if not doMakeDir(_path, mkdirCommand):
                sys.exit("Error creating directory: {}".format(_path))

        for _file in _value:
            basename = os.path.basename(_file)
            doFileTransfer(_file, os.path.join(_path, basename), transferCommand)

def cleanup(directory, dryRun=False):
    print("todo")

def get_date_taken(path):
    filename, fileExtension = os.path.splitext(path)
    if fileExtension.lower() in RAW_NAME or fileExtension.lower() in JPG_NAME:
        f = open(path, mode='rb')
        tags = exifread.process_file(f, details=False, stop_tag="Image DateTime")
        f.close()
        return tags["Image DateTime"].values
    elif fileExtension.lower() in JPG_NAME:
        return Image.open(path)._getexif()[36867]

FUNCTION_MAP = {
    "organize" : organizeInPlace,
    "import" : importFilesFromCard,
    "cleanup" : cleanup,
}

TRANSFER_FUNC_MAP = {
    "copy": copyfile,
    "move": os.rename,
    "dryRun": lambda src, dest: logger.debug("{} -> {}".format(src, dest))
}
parser = argparse.ArgumentParser(description="Utility for managing the Pictures directory.")
parser.add_argument("-d", help="Set debug output.", action='store_true', dest='dryRun')
subparsers = parser.add_subparsers(help="Commands", dest="command")
subparsers.required = True
organizeParser = subparsers.add_parser("organize", help="Organize an existing Camera Roll directory to conform to the standard.")
organizeParser.add_argument("directory",
                          #type=argparse.FileType('rb'),
                          type=str,
                          )

importParser = subparsers.add_parser("import", help="Import pictures from an external source to the camera roll.")
importParser.add_argument("directory",
                          help="The directories. import <importDirectory> <outputDirectory>",
                          #type=argparse.FileType('rb'),
                          type=str,
                          nargs=2
                          )

cleanupParser = subparsers.add_parser("cleanup", help="Cleanup any JPG images in the Camera Roll that correspond with deleted raw files.")
cleanupParser.add_argument("directory",
                          #type=argparse.FileType('rb'),
                          type=str,
                          )

args = parser.parse_args()
if args.dryRun:
    logger.setLevel(logging.DEBUG)
    transferFunc = TRANSFER_FUNC_MAP['dryRun']
    mkdirFunc = lambda dest: logger.debug("mkdir {}".format(dest))
else:
    transferFunc = TRANSFER_FUNC_MAP[args.command]
    mkdirFunc = os.makedirs
    logger.setLevel(logging.ERROR)

logger.debug(args.directory)
FUNCTION_MAP[args.command](args.directory, transferFunc, mkdirFunc)
