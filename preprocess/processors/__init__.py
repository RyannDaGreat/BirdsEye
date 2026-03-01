"""
Auto-discovers all processor modules in this directory.
Adding a new processor = dropping a .py file here. No registration needed.

Validates on load:
- No duplicate processor names
- No artifact filename collisions between processors
- No field name collisions between processors
"""

import os
import importlib
from .base import Processor


def discover_processors():
    """
    Scan processors/ directory, import all modules, return {name: processor_instance}.

    Validates no collisions between processors. Raises ValueError on conflict.
    Prints which plugins are loaded.

    Pure function (reads filesystem but is deterministic).
    """
    processors = {}
    pkg_dir = os.path.dirname(__file__)
    for filename in sorted(os.listdir(pkg_dir)):
        if filename.endswith('.py') and filename not in ('__init__.py', 'base.py'):
            module_name = filename[:-3]
            mod = importlib.import_module(f'.{module_name}', package='preprocess.processors')
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (isinstance(attr, type) and issubclass(attr, Processor)
                    and attr is not Processor and hasattr(attr, 'name')
                    and attr.name):
                    instance = attr()
                    processors[instance.name] = instance

    _validate_no_collisions(processors)

    # Print loaded plugins
    names = sorted(processors.keys())
    print(f"Loaded {len(names)} processors: {', '.join(names)}")
    for name in names:
        proc = processors[name]
        deps = proc.depends_on if proc.depends_on else "(none)"
        n_artifacts = len(proc.artifacts)
        n_fields = len(proc.fields)
        print(f"  {name}: {proc.human_name} | depends_on={deps} | {n_artifacts} artifacts, {n_fields} fields")

    return processors


def _validate_no_collisions(processors):
    """
    Check that no two processors share artifact filenames, field names, or
    vector_index prefixes. Raises ValueError on conflict.

    Pure function.

    >>> _validate_no_collisions({})  # empty is fine
    """
    artifact_owners = {}  # filename -> processor name
    field_owners = {}     # field_name -> processor name
    prefix_owners = {}    # vector_index prefix -> processor name

    for proc_name, proc in processors.items():
        for artifact in proc.artifacts:
            fn = artifact["filename"]
            if fn in artifact_owners:
                raise ValueError(
                    f"Artifact filename collision: '{fn}' is produced by both "
                    f"'{artifact_owners[fn]}' and '{proc_name}'"
                )
            artifact_owners[fn] = proc_name

        for field_name in proc.fields:
            if field_name in field_owners:
                raise ValueError(
                    f"Field name collision: '{field_name}' is produced by both "
                    f"'{field_owners[field_name]}' and '{proc_name}'"
                )
            field_owners[field_name] = proc_name

        for rule in getattr(proc, 'aggregation', []):
            if rule["type"] == "vector_index":
                prefix = rule["prefix"]
                if prefix in prefix_owners:
                    raise ValueError(
                        f"Vector index prefix collision: '{prefix}' is used by both "
                        f"'{prefix_owners[prefix]}' and '{proc_name}'"
                    )
                prefix_owners[prefix] = proc_name


def resolve_dependencies(enabled_names, all_processors):
    """
    Add all transitive dependencies and return in topological order.

    Pure function.

    >>> class A: name='a'; depends_on=[]
    >>> class B: name='b'; depends_on=['a']
    >>> resolve_dependencies({'b'}, {'a': A(), 'b': B()})
    ['a', 'b']
    """
    resolved = []
    visited = set()

    def visit(name):
        if name in visited:
            return
        visited.add(name)
        proc = all_processors[name]
        for dep in proc.depends_on:
            if dep not in all_processors:
                raise ValueError(f"Processor '{name}' depends on unknown processor '{dep}'")
            visit(dep)
        resolved.append(name)

    for name in sorted(enabled_names):
        visit(name)

    return resolved


def collect_field_info(processors):
    """
    Collect all field metadata from all processors into one dict.

    Pure function.

    >>> collect_field_info({})
    {}
    """
    fields = {}
    for proc in processors.values():
        fields.update(proc.fields)
    return fields


def collect_aggregation_rules(processors):
    """
    Collect all aggregation rules from all processors, grouped by type.

    Returns (json_dict_rules, vector_index_rules) where:
      - json_dict_rules: {target_filename: [(source_filename, proc_name), ...]}
      - vector_index_rules: [{prefix, source, dim, proc_name}, ...]

    Pure function.

    >>> collect_aggregation_rules({})
    ({}, [])
    """
    json_dict_rules = {}
    vector_index_rules = []

    for proc_name, proc in processors.items():
        for rule in getattr(proc, 'aggregation', []):
            if rule["type"] == "json_dict":
                target = rule["target"]
                source = rule["source"]
                json_dict_rules.setdefault(target, []).append((source, proc_name))
            elif rule["type"] == "vector_index":
                vector_index_rules.append({
                    "prefix": rule["prefix"],
                    "source": rule["source"],
                    "dim": rule["dim"],
                    "proc_name": proc_name,
                })

    return json_dict_rules, vector_index_rules


def collect_text_encoders(processors):
    """
    Discover text encoders from processors that declare embedding_space.

    Returns {prefix: encode_text_callable}.

    Pure function.

    >>> collect_text_encoders({})
    {}
    """
    encoders = {}
    for proc_name, proc in processors.items():
        if (getattr(proc, 'embedding_space', None)
                and type(proc).encode_text is not Processor.encode_text):
            prefix = proc.embedding_space["prefix"]
            encoders[prefix] = type(proc).encode_text
    return encoders


def collect_artifact_info(processors):
    """
    Collect all artifact metadata from all processors, split by type.

    Returns (image_artifacts, data_artifacts) where each is {filename: artifact_dict}.
    Pure function.

    >>> collect_artifact_info({})
    ({}, {})
    """
    image_artifacts = {}
    data_artifacts = {}
    for proc in processors.values():
        for a in proc.artifacts:
            if a.get("type") == "image":
                image_artifacts[a["filename"]] = a
            elif a.get("type") == "data":
                data_artifacts[a["filename"]] = a
    return image_artifacts, data_artifacts
