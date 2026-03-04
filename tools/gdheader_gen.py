#!/usr/bin/env python3
"""
GDExtension Header Generator
Scans src/ for headers using GD_GENERATED_BODY() and GDPROPERTY() annotations,
then generates .gen.h (GD_GENERATED_BODY macro redefinition) and .gen.cpp (implementations).

Run manually:   python tools/gdheader_gen.py
Runs automatically via SConstruct on every build.
"""

import re
import os
from dataclasses import dataclass

# Maps C++ types to Godot Variant::Type enum values
TYPE_MAP = {
    'float':    'FLOAT',
    'double':   'FLOAT',
    'int':      'INT',
    'bool':     'BOOL',
    'String':   'STRING',
    'Vector2':  'VECTOR2',
    'Vector3':  'VECTOR3',
    'Color':    'COLOR',
    'NodePath': 'NODE_PATH',
}

# Lifecycle methods: (godot_name, user_name, params_decl, params_call)
LIFECYCLE = [
    ('_ready',            'ready',            '',             ''),
    ('_process',          'process',          'double delta', 'delta'),
    ('_physics_process',  'physics_process',  'double delta', 'delta'),
]

def is_node_ref(cpp_type):
    return cpp_type.endswith('*')

def is_ref_type(cpp_type):
    return cpp_type.startswith('Ref<')

def ref_inner_type(cpp_type):
    return cpp_type[4:-1]  # Strip 'Ref<' and '>'

def is_lifecycle_method(method_name):
    return method_name.endswith('*')

def node_type_name(cpp_type):
    return cpp_type.rstrip('*').strip()

def type_to_include(cpp_type, is_godot_type=True):
    t = node_type_name(cpp_type)
    if is_godot_type:
        s = re.sub(r'([a-z])([A-Z])', r'\1_\2', t)
        return f'godot_cpp/classes/{s.lower()}.hpp'
    else:
        # For custom types, find the header file
        return find_header_for_type(t)

def ref_type_to_include(cpp_type):
    """Get include path for a Ref<Type>. Check custom classes first, then Godot."""
    inner = ref_inner_type(cpp_type)

    # First, check if it's a custom class in the project
    custom_header = find_header_for_type(inner)
    if custom_header:
        return custom_header

    # Fall back to Godot class naming convention
    s = re.sub(r'([a-z])([A-Z])', r'\1_\2', inner)
    return f'godot_cpp/classes/{s.lower()}.hpp'

def find_header_for_type(type_name):
    """Find the relative path to the header file for a given class name."""
    # Search for the class definition in src/
    for root, dirs, files in os.walk('src'):
        for file in files:
            if file.endswith('.h') and not file.endswith('.gen.h'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if re.search(rf'class\s+{type_name}\s*[:{{\s]', content):
                        # Return path relative to src/
                        rel_path = os.path.relpath(filepath, 'src').replace('\\', '/')
                        return rel_path
    return None

def get_variant_type(cpp_type):
    return TYPE_MAP.get(cpp_type, 'NIL')

def is_godot_class(class_name):
    """Check if a class is a Godot engine class."""
    # Known Godot classes from godot_cpp
    godot_classes = {
        'Node', 'Node2D', 'Node3D', 'Control', 'CanvasItem', 'Viewport',
        'Window', 'SceneTree', 'Resource', 'RefCounted', 'Object',
        'RigidBody3D', 'CharacterBody3D', 'PhysicsBody3D', 'CollisionObject3D',
        'Camera3D', 'Light3D', 'OmniLight3D', 'DirectionalLight3D', 'SpotLight3D',
        'MeshInstance3D', 'AnimatedSprite3D', 'Sprite3D',
    }
    return class_name in godot_classes

def find_godot_base_class(class_name, visited=None):
    """Walk up the inheritance chain to find the first Godot base class.
    Returns the Godot class name, or None if not found."""
    if visited is None:
        visited = set()

    if class_name in visited:
        return None
    visited.add(class_name)

    # Check if this is already a Godot class
    if is_godot_class(class_name):
        return class_name

    # Find the parent of this class
    parent = None
    for root, dirs, files in os.walk('src'):
        for file in files:
            if file.endswith('.h') and not file.endswith('.gen.h'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    match = re.search(rf'class\s+{re.escape(class_name)}\s*:\s*(?:(?:public|private|protected)\s+)?(\w+)[^{{]*\{{', content)
                    if match:
                        parent = match.group(1)
                        break
        if parent:
            break

    if parent:
        return find_godot_base_class(parent, visited)

    return None

@dataclass
class ParsedHeader:
    class_name: str
    parent_name: str
    godot_base_class: str  # The actual Godot class in the hierarchy
    properties: list
    functions: list
    signals: list
    lifecycle_methods: list
    lifecycle_editor_methods: list
    is_abstract: bool = False 

def parse_class_declaration(content):
    """Extract class name and parent class from header.
    Handles any inheritance access level: public, private, protected, or none."""
    class_match = re.search(r'class\s+(\w+)\s*:\s*(?:(?:public|private|protected)\s+)?(\w+)[^;]*\{', content)
    if not class_match:
        return None, None
    return class_match.group(1), class_match.group(2)

def parse_properties(content):
    """Extract GDPROPERTY declarations."""
    prop_re = re.compile(r'GDPROPERTY\s*\(\s*\)\s+(Ref<[\w:]+>|[\w:]+\*?)\s+(\w+)\s*(?:=\s*[^;]+)?;')
    return prop_re.findall(content)

def parse_functions(content):
    """Extract GDFUNCTION declarations."""
    func_re = re.compile(r'GDFUNCTION\s*\(\s*\)\s+(\w+)\s+(\w+)\s*\(([^)]*)\)\s*;')
    return func_re.findall(content)

def parse_signals(content):
    """Extract GDSIGNAL declarations."""
    signal_re = re.compile(r'GDSIGNAL\s*\(\s*"([^"]+)"\s*,([^)]*)\)')
    return signal_re.findall(content)

def parse_lifecycle_methods(content):
    """Detect lifecycle methods (ready, process, physics_process) declared in header."""
    lifecycle_methods = []
    lifecycle_editor_methods = []
    lifecycle_names = set(user_name for _, user_name, _, _ in LIFECYCLE)

    # Match method declarations like "void ready();" or "void process(double delta);"
    method_decl_re = re.compile(r'void\s+(\w+)\s*\([^)]*\)\s*;')

    for match in method_decl_re.finditer(content):
        method_name = match.group(1)

        # Check if this matches a lifecycle method directly
        if method_name in lifecycle_names:
            for godot_name, user_name, params_decl, params_call in LIFECYCLE:
                if user_name == method_name:
                    lifecycle_methods.append((godot_name, user_name, params_decl, params_call))
                    break
        # Or if it's an _editor variant of a lifecycle method
        elif method_name.endswith('_editor'):
            base_name = method_name[:-7]  # Remove '_editor'
            if base_name in lifecycle_names:
                for godot_name, user_name, params_decl, params_call in LIFECYCLE:
                    if user_name == base_name:
                        lifecycle_editor_methods.append((godot_name, method_name, params_decl, params_call))
                        break

    return lifecycle_methods, lifecycle_editor_methods

def collect_inherited_lifecycle_methods(parent_name, own_user_names, visited=None):
    """Walk parent classes to find lifecycle methods not declared in the current (concrete) class.
    Returns a list of (godot_name, user_name, params_decl, params_call) tuples."""
    if visited is None:
        visited = set()
    if not parent_name or parent_name in visited or is_godot_class(parent_name):
        return []
    visited.add(parent_name)

    for root, _, files in os.walk('src'):
        for file in files:
            if not file.endswith('.h') or file.endswith('.gen.h'):
                continue
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            if not re.search(rf'class\s+{re.escape(parent_name)}\s*[:{{\s]', content):
                continue
            # Found the parent's header — collect its lifecycle methods
            lifecycle, _ = parse_lifecycle_methods(content)
            inherited = [(g, u, pd, pc) for g, u, pd, pc in lifecycle if u not in own_user_names]
            for entry in inherited:
                own_user_names.add(entry[1])
            # Recurse into grandparent
            match = re.search(
                rf'class\s+{re.escape(parent_name)}\s*:\s*(?:(?:public|private|protected)\s+)?(\w+)[^{{]*\{{',
                content)
            grandparent = match.group(1) if match else None
            inherited += collect_inherited_lifecycle_methods(grandparent, own_user_names, visited)
            return inherited
    return []

def is_abstract_class(content):
    """Check if a class has any pure virtual methods (= 0)."""
    # Match any method declaration ending with = 0;
    pure_virtual_re = re.compile(r'virtual\s+\w+[\s\*&]*\w+\s*\([^)]*\)\s*=\s*0\s*;')
    return bool(pure_virtual_re.search(content))

def parse_header(filepath):
    """Parse a GDExtension header file and extract class information."""
    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    if 'GD_GENERATED_BODY' not in content:
        return None

    class_name, parent_name = parse_class_declaration(content)
    if not class_name or not parent_name:
        return None

    # Find the actual Godot base class in the inheritance chain
    godot_base = find_godot_base_class(class_name)
    if not godot_base:
        # Skip generation if no Godot base class found
        return None

    properties = parse_properties(content)
    functions = parse_functions(content)
    signals = parse_signals(content)
    lifecycle_methods, editor_methods = parse_lifecycle_methods(content)
    abstract = is_abstract_class(content)

    # For concrete classes, inherit lifecycle methods from abstract parent classes so the
    # generator can emit properly-typed overrides (avoids godot_cpp template deduction errors)
    if not abstract:
        own_user_names = {u for _, u, _, _ in lifecycle_methods}
        lifecycle_methods += collect_inherited_lifecycle_methods(parent_name, own_user_names)

    return ParsedHeader(class_name, parent_name, godot_base, properties, functions, signals, lifecycle_methods, editor_methods, abstract)

def ensure_gen_include(filepath, base_name, rel_dir):
    include_path = f'generated/{rel_dir}/{base_name}.gen.h' if rel_dir != '.' else f'generated/{base_name}.gen.h'
    gen_include = f'#include "{include_path}"'
    with open(filepath, encoding='utf-8') as f:
        lines = f.readlines()
    if any(gen_include in line for line in lines):
        return
    insert_pos = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('#include'):
            insert_pos = i + 1
        if stripped.startswith('namespace') or re.match(r'class\s+\w+', stripped):
            break
    lines.insert(insert_pos, gen_include + '\n')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f'[gdheader_gen] Inserted {gen_include} into {os.path.basename(filepath)}')

def build_method_params_string(parameters_array):
    params = []
    for raw_parameter in parameters_array.split(','):
        parts = raw_parameter.strip().split()
        if len(parts) == 2:
            params.append(f'"{parts[1]}"')
    params_string = ', '.join(params)
    if params:
        params_string = ', ' + params_string
    return params_string

def build_signal_params_string(parameters_array):
    types = []
    names = []
    params_string = ''
    for i, raw_parameter in enumerate(parameters_array.split(',')):
        if i % 2 == 0:
            types.append(raw_parameter.strip())
        else:
            names.append(raw_parameter.strip())
    for i, t in enumerate(types):
        variant_type = get_variant_type(t)
        name = names[i] if i < len(names) else f'param{i}'
        params_string += f', PropertyInfo(Variant::{variant_type}, "{name}")'
    return params_string

def build_header_macro_lines(parsed: ParsedHeader):
    """Build the list of lines for the GD_GENERATED_BODY macro."""
    node_refs   = [(t, n) for t, n in parsed.properties if is_node_ref(t)]
    ref_types   = [(t, n) for t, n in parsed.properties if is_ref_type(t)]
    value_props = [(t, n) for t, n in parsed.properties if not is_node_ref(t) and not is_ref_type(t)]

    lines = [
        f'    GDCLASS({parsed.class_name}, {parsed.godot_base_class})',
        'protected:',
        '    static void _bind_methods();',
    ]

    # Private: NodePath storage for node-ref properties (concrete classes only)
    if not parsed.is_abstract and node_refs:
        lines.append('private:')
        for _, prop_name in node_refs:
            lines.append(f'    NodePath _{prop_name}_path;')

    lines.append('public:')

    # Lifecycle overrides: concrete classes only (avoids template deduction issues in godot_cpp)
    if not parsed.is_abstract:
        has_ready = any(godot_name == '_ready' for godot_name, _, _, _ in parsed.lifecycle_methods)
        if node_refs and not has_ready:
            lines.append('    void _ready() override;')

        for godot_name, _, params_decl, _ in parsed.lifecycle_methods:
            p = f'({params_decl})' if params_decl else '()'
            lines.append(f'    void {godot_name}{p} override;')

    # Value property getters/setters
    for cpp_type, prop_name in value_props:
        lines.append(f'    {cpp_type} get_{prop_name}() const;')
        lines.append(f'    void set_{prop_name}({cpp_type} val);')

    # Ref<T> getters/setters
    for cpp_type, prop_name in ref_types:
        lines.append(f'    {cpp_type} get_{prop_name}() const;')
        lines.append(f'    void set_{prop_name}({cpp_type} val);')

    # Node-ref NodePath getters/setters + _resolve_node_paths
    for _, prop_name in node_refs:
        lines.append(f'    NodePath get_{prop_name}_path() const;')
        lines.append(f'    void set_{prop_name}_path(NodePath val);')
    # Add _resolve_node_paths declaration only if there are node refs
    if node_refs:
        lines.append('    void _resolve_node_paths();')

    return lines

def write_gen_h(parsed: ParsedHeader, out_dir, base_name, subdir):
    macro_lines = build_header_macro_lines(parsed)

    # Build macro with line continuations
    macro_body_lines = []
    for i, line in enumerate(macro_lines):
        suffix = ' \\' if i < len(macro_lines) - 1 else ''
        macro_body_lines.append(line + suffix)

    gen_h_content = (
        '// AUTO-GENERATED by tools/gdheader_gen.py — do not edit\n'
        '#undef GD_GENERATED_BODY\n'
        '#define GD_GENERATED_BODY() \\\n' +
        '\n'.join(macro_body_lines) + '\n'
    )

    gen_h_path = os.path.join(out_dir, subdir, f'{base_name}.gen.h').replace('\\', '/') if subdir != '.' else os.path.join(out_dir, f'{base_name}.gen.h').replace('\\', '/')
    os.makedirs(os.path.dirname(gen_h_path), exist_ok=True)
    with open(gen_h_path, 'w', encoding='utf-8') as f:
        f.write(gen_h_content)

def build_cpp_property_implementations(parsed: ParsedHeader):
    """Generate property getter/setter implementations."""
    node_refs   = [(t, n) for t, n in parsed.properties if is_node_ref(t)]
    ref_types   = [(t, n) for t, n in parsed.properties if is_ref_type(t)]
    value_props = [(t, n) for t, n in parsed.properties if not is_node_ref(t) and not is_ref_type(t)]
    lines = []

    # Value property getters/setters
    for cpp_type, prop_name in value_props:
        lines.append(f'{cpp_type} {parsed.class_name}::get_{prop_name}() const {{ return {prop_name}; }}\n')
        lines.append(f'void {parsed.class_name}::set_{prop_name}({cpp_type} val) {{ {prop_name} = val; }}\n')

    # Ref<T> getters/setters
    for cpp_type, prop_name in ref_types:
        lines.append(f'{cpp_type} {parsed.class_name}::get_{prop_name}() const {{ return {prop_name}; }}\n')
        lines.append(f'void {parsed.class_name}::set_{prop_name}({cpp_type} val) {{ {prop_name} = val; }}\n')

    # Node-ref NodePath getters/setters
    for _, prop_name in node_refs:
        lines.append(f'NodePath {parsed.class_name}::get_{prop_name}_path() const {{ return _{prop_name}_path; }}\n')
        lines.append(f'void {parsed.class_name}::set_{prop_name}_path(NodePath val) {{ _{prop_name}_path = val; }}\n')

    return lines

def build_cpp_resolve_node_paths(parsed: ParsedHeader):
    """Generate _resolve_node_paths implementation."""
    node_refs = [(t, n) for t, n in parsed.properties if is_node_ref(t)]
    lines = []

    # Only generate if there are node references to resolve
    if not node_refs:
        return lines

    lines.append(f'\nvoid {parsed.class_name}::_resolve_node_paths() {{\n')
    for cpp_type, prop_name in node_refs:
        t = node_type_name(cpp_type)
        lines.append(f'    {prop_name} = get_node<{t}>(_{prop_name}_path);\n')
    lines.append(f'}}\n')

    return lines

def build_cpp_lifecycle_wrappers(parsed: ParsedHeader):
    """Generate Godot lifecycle method overrides."""
    node_refs = [(t, n) for t, n in parsed.properties if is_node_ref(t)]
    lines = ['\n']

    # Generate _ready if user didn't declare it and there are node refs to resolve
    has_ready = any(godot_name == '_ready' for godot_name, _, _, _ in parsed.lifecycle_methods)
    if node_refs and not has_ready:
        lines.append(f'void {parsed.class_name}::_ready() {{\n')
        lines.append(f'    _resolve_node_paths();\n')
        lines.append(f'}}\n\n')

    for godot_name, user_name, params_decl, params_call in parsed.lifecycle_methods:
        p_decl = f'({params_decl})' if params_decl else '()'

        lines.append(f'void {parsed.class_name}::{godot_name}{p_decl} {{\n')

        # Call _resolve_node_paths in _ready (only if there are node refs)
        if godot_name == '_ready' and node_refs:
            lines.append(f'    _resolve_node_paths();\n')

        lines.append(f'    if (Engine::get_singleton()->is_editor_hint()) {{\n')

        if(has_editor_lifecycle_method_defined(user_name, parsed)):
                lines.append(f'        {user_name}_editor({params_call});\n')
        lines.append(f'        return;\n')
        lines.append(f'    }}\n')

        lines.append(f'    {user_name}({params_call});\n')

        lines.append(f'}}\n\n')

    return lines

def has_editor_lifecycle_method_defined(method_name, parsed: ParsedHeader): 
    editor_name = method_name + "_editor"
    for _, user_name, _, _ in parsed.lifecycle_editor_methods:
        if user_name == editor_name:
            return True
    return False

def build_cpp_bind_methods(parsed: ParsedHeader):
    """Generate _bind_methods implementation."""
    node_refs   = [(t, n) for t, n in parsed.properties if is_node_ref(t)]
    ref_types   = [(t, n) for t, n in parsed.properties if is_ref_type(t)]
    value_props = [(t, n) for t, n in parsed.properties if not is_node_ref(t) and not is_ref_type(t)]

    # Filter out lifecycle methods from the functions list
    lifecycle_names = set(user_name for _, user_name, _, _ in parsed.lifecycle_methods)
    regular_functions = [(t, n, p) for t, n, p in parsed.functions if n not in lifecycle_names]

    lines = [f'void {parsed.class_name}::_bind_methods() {{\n']

    for cpp_type, prop_name in value_props:
        variant_type = get_variant_type(cpp_type)
        lines.append(f'    ClassDB::bind_method(D_METHOD("get_{prop_name}"), &{parsed.class_name}::get_{prop_name});\n')
        lines.append(f'    ClassDB::bind_method(D_METHOD("set_{prop_name}", "{prop_name}"), &{parsed.class_name}::set_{prop_name});\n')
        lines.append(f'    ADD_PROPERTY(PropertyInfo(Variant::{variant_type}, "{prop_name}"), "set_{prop_name}", "get_{prop_name}");\n')

    for cpp_type, prop_name in ref_types:
        inner = ref_inner_type(cpp_type)
        lines.append(f'    ClassDB::bind_method(D_METHOD("get_{prop_name}"), &{parsed.class_name}::get_{prop_name});\n')
        lines.append(f'    ClassDB::bind_method(D_METHOD("set_{prop_name}", "{prop_name}"), &{parsed.class_name}::set_{prop_name});\n')
        lines.append(f'    ADD_PROPERTY(PropertyInfo(Variant::OBJECT, "{prop_name}", PROPERTY_HINT_RESOURCE_TYPE, "{inner}"), "set_{prop_name}", "get_{prop_name}");\n')

    for cpp_type, prop_name in node_refs:
        t = node_type_name(cpp_type)
        lines.append(f'    ClassDB::bind_method(D_METHOD("get_{prop_name}_path"), &{parsed.class_name}::get_{prop_name}_path);\n')
        lines.append(f'    ClassDB::bind_method(D_METHOD("set_{prop_name}_path", "{prop_name}_path"), &{parsed.class_name}::set_{prop_name}_path);\n')
        lines.append(f'    ADD_PROPERTY(PropertyInfo(Variant::NODE_PATH, "{prop_name}_path", PROPERTY_HINT_NODE_PATH_VALID_TYPES, "{t}"), "set_{prop_name}_path", "get_{prop_name}_path");\n')

    for signal_name, signal_parameters in parsed.signals:
        lines.append(f'    ADD_SIGNAL(MethodInfo("{signal_name}"{build_signal_params_string(signal_parameters)}));\n')

    for _, method_name, parameters in regular_functions:
        lines.append(f'    ClassDB::bind_method(D_METHOD("{method_name}"{build_method_params_string(parameters)}), &{parsed.class_name}::{method_name});\n')

    lines.append('}\n\n')
    return lines

def write_gen_cpp(parsed: ParsedHeader, out_dir, base_name, header_include, subdir):
    node_refs = [(t, n) for t, n in parsed.properties if is_node_ref(t)]
    ref_types = [(t, n) for t, n in parsed.properties if is_ref_type(t)]

    lines_cpp = [
        f'// AUTO-GENERATED by tools/gdheader_gen.py — do not edit\n',
        f'#include "{header_include}"\n',
        f'#include "internal/class_registry.h"\n',
        f'#include <godot_cpp/classes/engine.hpp>\n',
    ]
    for cpp_type, _ in node_refs:
        type_name = node_type_name(cpp_type)
        header = find_header_for_type(type_name)
        if header:
            lines_cpp.append(f'#include "{header}"\n')
        else:
            lines_cpp.append(f'#include <{type_to_include(cpp_type, is_godot_type=True)}>\n')
    for cpp_type, _ in ref_types:
        lines_cpp.append(f'#include <{ref_type_to_include(cpp_type)}>\n')
    lines_cpp += ['\n', 'using namespace godot;\n', '\n']

    if parsed.is_abstract:
        # Abstract classes: only empty _bind_methods (required by GDCLASS, no registration)
        lines_cpp.append(f'void {parsed.class_name}::_bind_methods() {{}}\n\n')
    else:
        # Property implementations
        lines_cpp.extend(build_cpp_property_implementations(parsed))

        # Node path resolution
        lines_cpp.extend(build_cpp_resolve_node_paths(parsed))

        # Lifecycle method overrides
        lines_cpp.extend(build_cpp_lifecycle_wrappers(parsed))

        # Method binding
        lines_cpp.extend(build_cpp_bind_methods(parsed))

        # Class registration
        lines_cpp.append(
            f'namespace {{\n'
            f'    bool _registered_{parsed.class_name} = []() {{\n'
            f'        godot::ClassRegistry::get().add([]() {{ GDREGISTER_CLASS({parsed.class_name}); }});\n'
            f'        return true;\n'
            f'    }}();\n'
            f'}}\n'
        )

    gen_cpp_path = os.path.join(out_dir, subdir, f'{base_name}.gen.cpp').replace('\\', '/') if subdir != '.' else os.path.join(out_dir, f'{base_name}.gen.cpp').replace('\\', '/')
    os.makedirs(os.path.dirname(gen_cpp_path), exist_ok=True)
    with open(gen_cpp_path, 'w', encoding='utf-8') as f:
        f.writelines(lines_cpp)

def cleanup_orphaned_generated_files(src_dir, out_dir):
    """Delete .gen.h and .gen.cpp files that don't have corresponding source headers."""
    generated_to_keep = set()

    # First pass: find all source headers that should have generated files
    for root, _, files in os.walk(src_dir):
        for filename in files:
            if not filename.endswith('.h') or filename.endswith('.gen.h'):
                continue
            filepath = os.path.join(root, filename)
            if parse_header(filepath) is not None:
                base_name = os.path.splitext(filename)[0]
                rel_dir = os.path.relpath(os.path.dirname(filepath), src_dir).replace('\\', '/')
                gen_h = os.path.join(out_dir, rel_dir, f'{base_name}.gen.h').replace('\\', '/')
                gen_cpp = os.path.join(out_dir, rel_dir, f'{base_name}.gen.cpp').replace('\\', '/')
                generated_to_keep.add(gen_h)
                generated_to_keep.add(gen_cpp)

    # Second pass: delete orphaned generated files
    if os.path.exists(out_dir):
        for root, dirs, files in os.walk(out_dir):
            for filename in files:
                if filename.endswith('.gen.h') or filename.endswith('.gen.cpp'):
                    filepath = os.path.join(root, filename).replace('\\', '/')
                    if filepath not in generated_to_keep:
                        os.remove(filepath)
                        print(f'[gdheader_gen] Deleted orphaned: {filepath}')

def generate(src_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for root, dirs, files in os.walk(src_dir):
        for filename in files:
            if not filename.endswith('.h') or filename.endswith('.gen.h'):
                continue
            filepath = os.path.join(root, filename)
            parsed = parse_header(filepath)
            if not parsed:
                continue
            base_name = os.path.splitext(filename)[0]
            rel_dir = os.path.relpath(os.path.dirname(filepath), src_dir).replace('\\', '/')
            ensure_gen_include(filepath, base_name, rel_dir)
            write_gen_h(parsed, out_dir, base_name, rel_dir)
            header_include = os.path.relpath(filepath, src_dir).replace('\\', '/')
            write_gen_cpp(parsed, out_dir, base_name, header_include, rel_dir)
            props_info = f'{len(parsed.properties)} propert{"y" if len(parsed.properties) == 1 else "ies"}' if parsed.properties else 'no properties'
            output_path = f'generated/{rel_dir}/{base_name}.gen.h' if rel_dir != '.' else f'generated/{base_name}.gen.h'
            print(f'[gdheader_gen] {parsed.class_name} ({props_info}) -> {output_path} / .gen.cpp')

    # Clean up orphaned generated files
    cleanup_orphaned_generated_files(src_dir, out_dir)

if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(script_dir, '..', 'src')
    out_dir = os.path.join(src_dir, 'generated')
    generate(src_dir, out_dir)
