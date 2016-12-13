import ast
import hashlib
import inspect
import os
import os.path as op
import re
import time

from pyrevit import HOST_APP, PyRevitException

# noinspection PyUnresolvedReferences
from System import AppDomain
# noinspection PyUnresolvedReferences
from System.Diagnostics import Process
# noinspection PyUnresolvedReferences
from System.Reflection import Assembly


def enum(**enums):
    return type('Enum', (), enums)


class Timer:
    """Timer class using python native time module."""
    def __init__(self):
        self.start = time.time()

    def restart(self):
        self.start = time.time()

    def get_time(self):
        return time.time() - self.start


class ScriptFileParser:
    def __init__(self, file_address):
        self.file_addr = file_address
        try:
            with open(file_address, 'r') as f:
                self.ast_tree = ast.parse(f.read())
        except Exception as err:
            raise PyRevitException('Error parsing script file: {} | {}'.format(self.file_addr, err))

    def extract_param(self, param_name):
        try:
            for child in ast.iter_child_nodes(self.ast_tree):
                if hasattr(child, 'targets'):
                    for target in child.targets:
                        if hasattr(target, 'id') and target.id == param_name:
                            return ast.literal_eval(child.value)
        except Exception as err:
            raise PyRevitException('Error parsing parameter: {} in script file for : {} | {}'.format(param_name,
                                                                                                     self.file_addr,
                                                                                                     err))

        return None


def get_all_subclasses(parent_classes):
    sub_classes = []
    # if super-class, get a list of sub-classes. Otherwise use component_class to create objects.
    for parent_class in parent_classes:
        try:
            derived_classes = parent_class.__subclasses__()
            if len(derived_classes) == 0:
                sub_classes.append(parent_class)
            else:
                sub_classes.extend(derived_classes)
        except AttributeError:
            sub_classes.append(parent_class)
    return sub_classes


def get_sub_folders(search_folder):
    sub_folders = []
    for f in os.listdir(search_folder):
        if op.isdir(op.join(search_folder, f)):
            sub_folders.append(f)
    return sub_folders


def verify_directory(folder):
    """Checks if the folder exists and if not creates the folder.
    Returns OSError on folder making errors."""
    if not op.exists(folder):
        try:
            os.makedirs(folder)
        except OSError as err:
            raise err
    return True


def get_parent_directory(path):
    return op.dirname(path)


def join_strings(path_list):
    if path_list:
        return ';'.join(path_list)
    return ''


# character replacement list for cleaning up file names
SPECIAL_CHARS = {' ': '',
                 '~': '',
                 '!': 'EXCLAM',
                 '@': 'AT',
                 '#': 'NUM',
                 '$': 'DOLLAR',
                 '%': 'PERCENT',
                 '^': '',
                 '&': 'AND',
                 '*': 'STAR',
                 '+': 'PLUS',
                 ';': '', ':': '', ',': '', '\"': '', '{': '', '}': '', '[': '', ']': '', '\(': '', '\)': '',
                 '-': 'MINUS',
                 '=': 'EQUALS',
                 '<': '', '>': '',
                 '?': 'QMARK',
                 '.': 'DOT',
                 '_': 'UNDERS',
                 '|': 'VERT',
                 '\/': '', '\\': ''}


def cleanup_string(input_str):
    # remove spaces and special characters from strings
    for char, repl in SPECIAL_CHARS.items():
        input_str = input_str.replace(char, repl)

    return input_str


def get_revit_instance_count():
    return len(list(Process.GetProcessesByName(HOST_APP.proc_name)))


def run_process(proc, cwd=''):
    import subprocess
    return subprocess.Popen(proc, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, shell=True)


def inspect_calling_scope_local_var(variable_name):
    """Traces back the stack to find the variable in the caller local stack.
    Example:
    PyRevitLoader defines __revit__ in builtins and __window__ in locals. Thus, modules have access to
    __revit__ but not to __window__. This function is used to find __window__ in the caller stack.
    """
    frame = inspect.stack()[1][0]
    while variable_name not in frame.f_locals:
        frame = frame.f_back
        if frame is None:
            return None
    return frame.f_locals[variable_name]


def inspect_calling_scope_global_var(variable_name):
    """Traces back the stack to find the variable in the caller local stack.
    Example:
    PyRevitLoader defines __revit__ in builtins and __window__ in locals. Thus, modules have access to
    __revit__ but not to __window__. This function is used to find __window__ in the caller stack.
    """
    frame = inspect.stack()[1][0]
    while variable_name not in frame.f_globals:
        frame = frame.f_back
        if frame is None:
            return None
    return frame.f_locals[variable_name]


def find_loaded_asm(asm_info, by_partial_name=False, by_location=False):
    """

    Args:
        asm_info (str): name or location of the assembly
        by_partial_name (bool): returns all assemblies that include the asm_info
        by_location (bool): returns all assemblies with their location matching asm_info

    Returns:
        list: List of all loaded assemblies matching the provided info
              If only one assembly has been found, it returns the assembly.
              None will be returned if assembly is not loaded.
    """
    loaded_asm_list = []
    for loaded_assembly in AppDomain.CurrentDomain.GetAssemblies():
        if by_partial_name:
            if asm_info.lower() in str(loaded_assembly.GetName().Name).lower():
                loaded_asm_list.append(loaded_assembly)
        elif by_location:
            try:
                if op.normpath(loaded_assembly.Location) == op.normpath(asm_info):
                    loaded_asm_list.append(loaded_assembly)
            except:
                continue
        elif asm_info.lower() == str(loaded_assembly.GetName().Name).lower():
            loaded_asm_list.append(loaded_assembly)

    return loaded_asm_list


def load_asm(asm_name):
    return AppDomain.CurrentDomain.Load(asm_name)


def load_asm_file(asm_file):
    return Assembly.LoadFrom(asm_file)


def make_canonical_name(*args):
    return '.'.join(args)


def get_file_name(file_path):
    return op.splitext(op.basename(file_path))[0]


def get_str_hash(source_str):
    return hashlib.md5(source_str.encode('utf-8')).hexdigest()


def calculate_dir_hash(dir_path, dir_filter, file_filter):
    """Creates a unique hash # to represent state of directory."""
    mtime_sum = 0
    for root, dirs, files in os.walk(dir_path):
        if re.search(dir_filter, op.basename(root), flags=re.IGNORECASE):
            mtime_sum += op.getmtime(root)
            for filename in files:
                if re.search(file_filter, filename, flags=re.IGNORECASE):
                    modtime = op.getmtime(op.join(root, filename))
                    mtime_sum += modtime
    return get_str_hash(str(mtime_sum))


def prepare_html_str(input_string):
    return input_string.replace('<', '&clt;').replace('>', '&cgt;')
