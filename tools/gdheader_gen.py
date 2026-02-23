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

def is_lifecycle_method(method_name):
    return method_name.endswith('*')

def node_type_name(cpp_type):
    return cpp_type.rstrip('*').strip()

def type_to_include(cpp_type):
    t = node_type_name(cpp_type)
    s = re.sub(r'([a-z])([A-Z])', r'\1_\2', t)
    return f'godot_cpp/classes/{s.lower()}.hpp'

def get_variant_type(cpp_type):
    return TYPE_MAP.get(cpp_type, 'NIL')

@dataclass
class ParsedHeader:
    class_name: str
    parent_name: str
    properties: list
    functions: list
    signals: list
    lifecycle_methods: list
    lifecycle_editor_methods: list 

def parse_class_declaration(content):
    """Extract class name and parent class from header.
    Handles any inheritance access level: public, private, protected, or none."""
    class_match = re.search(r'class\s+(\w+)\s*:\s*(?:(?:public|private|protected)\s+)?(\w+)[^;]*\{', content)
    if not class_match:
        return None, None
    return class_match.group(1), class_match.group(2)

def parse_properties(content):
    """Extract GDPROPERTY declarations."""
    prop_re = re.compile(r'GDPROPERTY\s*\(\s*\)\s+([\w:]+\*?)\s+(\w+)\s*(?:=\s*[^;]+)?;')
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

def parse_header(filepath):
    """Parse a GDExtension header file and extract class information."""
    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    if 'GD_GENERATED_BODY' not in content:
        return None

    class_name, parent_name = parse_class_declaration(content)
    if not class_name or not parent_name:
        return None

    properties = parse_properties(content)
    functions = parse_functions(content)
    signals = parse_signals(content)
    lifecycle_methods, editor_methods = parse_lifecycle_methods(content)

    return ParsedHeader(class_name, parent_name, properties, functions, signals, lifecycle_methods, editor_methods)

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
    value_props = [(t, n) for t, n in parsed.properties if not is_node_ref(t)]

    lines = [
        f'    GDCLASS({parsed.class_name}, {parsed.parent_name})',
        'protected:',
        '    static void _bind_methods();',
    ]

    # Private: NodePath storage for node-ref properties
    if node_refs:
        lines.append('private:')
        for _, prop_name in node_refs:
            lines.append(f'    NodePath _{prop_name}_path;')

    lines.append('public:')

    # Override Godot lifecycle methods (public so the engine can call them)
    for godot_name, _, params_decl, _ in parsed.lifecycle_methods:
        p = f'({params_decl})' if params_decl else '()'
        lines.append(f'    void {godot_name}{p} override;')

    # Value property getters/setters
    for cpp_type, prop_name in value_props:
        lines.append(f'    {cpp_type} get_{prop_name}() const;')
        lines.append(f'    void set_{prop_name}({cpp_type} val);')

    # Node-ref NodePath getters/setters + _resolve_node_paths
    for _, prop_name in node_refs:
        lines.append(f'    NodePath get_{prop_name}_path() const;')
        lines.append(f'    void set_{prop_name}_path(NodePath val);')
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
    value_props = [(t, n) for t, n in parsed.properties if not is_node_ref(t)]
    lines = []

    # Value property getters/setters
    for cpp_type, prop_name in value_props:
        lines.append(f'{cpp_type} {parsed.class_name}::get_{prop_name}() const {{ return {prop_name}; }}\n')
        lines.append(f'void {parsed.class_name}::set_{prop_name}({cpp_type} val) {{ {prop_name} = val; }}\n')

    # Node-ref NodePath getters/setters
    for _, prop_name in node_refs:
        lines.append(f'NodePath {parsed.class_name}::get_{prop_name}_path() const {{ return _{prop_name}_path; }}\n')
        lines.append(f'void {parsed.class_name}::set_{prop_name}_path(NodePath val) {{ _{prop_name}_path = val; }}\n')

    return lines

def build_cpp_resolve_node_paths(parsed: ParsedHeader):
    """Generate _resolve_node_paths implementation if needed."""
    node_refs = [(t, n) for t, n in parsed.properties if is_node_ref(t)]
    lines = []

    if node_refs:
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

    for godot_name, user_name, params_decl, params_call in parsed.lifecycle_methods:
        p_decl = f'({params_decl})' if params_decl else '()'

        lines.append(f'void {parsed.class_name}::{godot_name}{p_decl} {{\n')
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
    value_props = [(t, n) for t, n in parsed.properties if not is_node_ref(t)]

    # Filter out lifecycle methods from the functions list
    lifecycle_names = set(user_name for _, user_name, _, _ in parsed.lifecycle_methods)
    regular_functions = [(t, n, p) for t, n, p in parsed.functions if n not in lifecycle_names]

    lines = [f'void {parsed.class_name}::_bind_methods() {{\n']

    for cpp_type, prop_name in value_props:
        variant_type = get_variant_type(cpp_type)
        lines.append(f'    ClassDB::bind_method(D_METHOD("get_{prop_name}"), &{parsed.class_name}::get_{prop_name});\n')
        lines.append(f'    ClassDB::bind_method(D_METHOD("set_{prop_name}", "{prop_name}"), &{parsed.class_name}::set_{prop_name});\n')
        lines.append(f'    ADD_PROPERTY(PropertyInfo(Variant::{variant_type}, "{prop_name}"), "set_{prop_name}", "get_{prop_name}");\n')

    for _, prop_name in node_refs:
        lines.append(f'    ClassDB::bind_method(D_METHOD("get_{prop_name}_path"), &{parsed.class_name}::get_{prop_name}_path);\n')
        lines.append(f'    ClassDB::bind_method(D_METHOD("set_{prop_name}_path", "{prop_name}_path"), &{parsed.class_name}::set_{prop_name}_path);\n')
        lines.append(f'    ADD_PROPERTY(PropertyInfo(Variant::NODE_PATH, "{prop_name}_path"), "set_{prop_name}_path", "get_{prop_name}_path");\n')

    for signal_name, signal_parameters in parsed.signals:
        lines.append(f'    ADD_SIGNAL(MethodInfo("{signal_name}"{build_signal_params_string(signal_parameters)}));\n')

    for _, method_name, parameters in regular_functions:
        lines.append(f'    ClassDB::bind_method(D_METHOD("{method_name}"{build_method_params_string(parameters)}), &{parsed.class_name}::{method_name});\n')

    lines.append('}\n\n')
    return lines

def write_gen_cpp(parsed: ParsedHeader, out_dir, base_name, header_include, subdir):
    node_refs = [(t, n) for t, n in parsed.properties if is_node_ref(t)]

    lines_cpp = [
        f'// AUTO-GENERATED by tools/gdheader_gen.py — do not edit\n',
        f'#include "{header_include}"\n',
        f'#include "internal/class_registry.h"\n',
        f'#include <godot_cpp/classes/engine.hpp>\n',
    ]
    for cpp_type, _ in node_refs:
        lines_cpp.append(f'#include <{type_to_include(cpp_type)}>\n')
    lines_cpp += ['\n', 'using namespace godot;\n', '\n']

    # Property implementations
    lines_cpp.extend(build_cpp_property_implementations(parsed))

    # Node path resolution
    lines_cpp.extend(build_cpp_resolve_node_paths(parsed))

    # Lifecycle method overrides
    lines_cpp.extend(build_cpp_lifecycle_wrappers(parsed))

    # Method binding
    lines_cpp.extend(build_cpp_bind_methods(parsed))

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

if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(script_dir, '..', 'src')
    out_dir = os.path.join(src_dir, 'generated')
    generate(src_dir, out_dir)
