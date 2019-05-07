from importlib import import_module


class JumpserverError(Exception):
    pass


class JumpserverAuthError(JumpserverError):
    pass


def import_string(dotted_path):
    """
    Import a dotted module path and return the attribute/class designated by the
    last name in the path. Raise ImportError if the import failed.

    :param dotted_path: path to import
    :return: imported class
    :raise: ImportError
    """
    try:
        module_path, class_name = dotted_path.rsplit('.', 1)
    except ValueError:
        msg = "%s doesn't look like a module path" % dotted_path
        raise ImportError(msg)

    module = import_module(module_path)

    try:
        return getattr(module, class_name)
    except AttributeError:
        msg = 'Module "%s" does not define a "%s" attribute/class' % (
            module_path, class_name)
        raise ImportError(msg)


def object_format(obj, attr_vars):
    if isinstance(obj, str):
        obj = obj.format(**attr_vars)
    elif isinstance(obj, list):
        obj = [object_format(v, attr_vars) for v in obj]
    elif isinstance(obj, dict):
        obj = {object_format(k, attr_vars): object_format(v, attr_vars) for k, v in obj.items()}
    return obj
