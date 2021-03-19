import sys
import os
import errno
import pkg_resources
import glob
import shutil

import inspect
import subprocess

# pin the version that we use in this test
# e.g. 1.0.3 has issues installing from a wheel on Windows
# not related to PythonEmbedInR
# https://stackoverflow.com/q/60767017
PANDAS_VERSION="1.0.1"

# pip main is not a public interface and is not programatically accessible
# in a stable way across python versions. the typical approach is to
# call pip in a subprocess using sys.executable, but running inside
# PythonEmbedInR sys.executable may not be what we want.
try:
    from pip import main as pipmain
except ImportError:
    from pip._internal import main as pipmain

def localSitePackageFolder(root):
    if os.name=='nt':
        # Windows
        return root+os.sep+"Lib"+os.sep+"site-packages"
    else:
        # Mac, Linux
        return root+os.sep+"lib"+os.sep+"python3.6"+os.sep+"site-packages"

def addLocalSitePackageToPythonPath(root):
    # PYTHONPATH sets the search path for importing python modules
    sitePackages = localSitePackageFolder(root)
    os.environ['PYTHONPATH'] = sitePackages
    sys.path.append(sitePackages)
    # modules with .egg extensions (such as future and synapseClient) need to be explicitly added to the sys.path
    for eggpath in glob.glob(sitePackages+os.sep+'*.egg'):
        os.environ['PYTHONPATH'] += os.pathsep+eggpath
        sys.path.append(eggpath)

def main(command, path):
    path = pkg_resources.normalize_path(path)
    moduleInstallationPrefix=path+os.sep+"inst"

    localSitePackages=localSitePackageFolder(moduleInstallationPrefix)
    
    addLocalSitePackageToPythonPath(moduleInstallationPrefix)

    if not os.path.exists(localSitePackages):
      os.makedirs(localSitePackages)

    if command == 'install':
      _pip_install(['pandas=={}'.format(PANDAS_VERSION)], localSitePackages)
    elif command == 'uninstall':
      print('uninstalling...')
      remove_dirs('pandas', localSitePackages)
    else:
      raise Exception("command not supported: "+command)

def _find_python_interpreter():
    # helper heuristic to find the bundled python interpreter binary associated
    # with PythonEmbedInR. we need it in order to be able to invoke pip via
    # a subprocess. it's not in the same place because of how we build
    # PythonEmbedInR differently between the OSes.

    possible_interpreter_filenames = [
        'python',
        'python{}'.format(sys.version_info.major),
        'python{}.{}'.format(sys.version_info.major, sys.version_info.minor),
    ]
    possible_interpreter_filenames.extend(['{}.exe'.format(f) for f in possible_interpreter_filenames])
    possible_interpreter_filenames.extend([os.path.join('bin', f).format(f) for f in possible_interpreter_filenames])

    last_path = None
    path = inspect.getfile(os)
    while(path and path != last_path):
        for f in possible_interpreter_filenames:
            file_path = os.path.join(path, f)
            if os.path.isfile(file_path) and os.access(file_path, os.X_OK):
                return file_path

        last_path = path
        path = os.path.dirname(path)

    # if we didn't find anything we'll hope there is any 'python3' interpreter on the path.
    # we're just going to use it to install some modules into a specific directory
    # so it doesn't actually even have to be the one bundled with PythonEmbedInR
    return 'python{}'.format(sys.version_info.major)

PYTHON_INTERPRETER = _find_python_interpreter()

def _pip_install(packages, localSitePackages):
    # the recommended way to call pip at runtime is by invoking a subprocess,
    # but that's complicated by the fact that we don't know where the python
    # interpreter is. usually you can do sys.executable but in the embedded
    # context sys.executable is R, not python. So we do a heuristic to
    # find the interpreter. this seems to work better here than calling main
    # on pip directly which doesn't work for some of these packages (separately
    # from the other issues above...)
    for package in packages:
        rc = subprocess.call([PYTHON_INTERPRETER, "-m", "pip", "install", package, "--upgrade", "--quiet", "--target", localSitePackages])
        if rc != 0:
            raise Exception("pip.main returned {} when installing {}".format(rc, package))

def remove_dirs(prefix, baseDir):
    to_remove = glob.iglob(os.path.join(baseDir, prefix+"*"))
    for path in to_remove:
      if os.path.isdir(path):
        shutil.rmtree(path)

