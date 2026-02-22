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

# Maps C++ types to Godot Variant::Type enum values
TYPE_MAP = {
    'float':   'FLOAT',
    'double':  'FLOAT',
    'int':     'INT',
    'bool':    'BOOL',
    'String':  'STRING',
    'Vector2': 'VECTOR2',
    'Vector3': 'VECTOR3',
    'Color':   'COLOR',
}


def parse_header(filepath):
    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    # Only process files that use GD_GENERATED_BODY
    if 'GD_GENERATED_BODY' not in content:
        return None

    # Find class name and parent from "class Foo : public Bar {"
    # Requires { to avoid matching forward declarations
    class_match = re.search(r'class\s+(\w+)\s*:\s*public\s+(\w+)[^;]*\{', content)
    if not class_match:
        return None

    class_name = class_match.group(1)
    parent_name = class_match.group(2)

    # Find GDPROPERTY() annotations followed by "type name;"
    prop_pattern = re.compile(r'GDPROPERTY\s*\(\s*\)\s+(\w+)\s+(\w+)\s*;')
    properties = prop_pattern.findall(content)  # list of (cpp_type, prop_name)

    # Find GDFUNCTION() annotations followed by "type name;"
    prop_pattern = re.compile(r'GDFUNCTION\s*\(\s*\)\s+(\w+)\s+(\w+)\s*\(([^)]*)\)\s*;')
    functions = prop_pattern.findall(content)  # list of (return type, function name, parameters)

    # Find GDFUNCTION() annotations followed by "type name;"
    prop_pattern = re.compile(r'GDSIGNAL\s*\(\s*"([^"]+)"\s*,([^)]*)\)')
    signals = prop_pattern.findall(content)  # list of (signal name, signal parameters  )

    return class_name, parent_name, properties, functions, signals


def ensure_gen_include(filepath, base_name):
    """Auto-insert #include "generated/xxx.gen.h" after the last #include, if not already present."""
    gen_include = f'#include "generated/{base_name}.gen.h"'

    with open(filepath, encoding='utf-8') as f:
        lines = f.readlines()

    if any(gen_include in line for line in lines):
        return  # already present

    # Insert after the last #include line, before namespace or class definition
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
        params.append(f'"{raw_parameter.split()[1]}"')

    params_string = ', '.join(params)
    if len(params) > 0:
        params_string = ', ' + params_string
    return params_string

def build_signal_params_string(parameters_array):
    types = []
    names = []

    params_string = ''
    for i, raw_parameter in enumerate(parameters_array.split(',')):
        if i % 2 == 0:
            types.append(raw_parameter)
        else:
            names.append(raw_parameter)

    for i, type in enumerate(types):
        variant_type = TYPE_MAP.get(types[i].strip(), 'NIL')
        params_string += f', PropertyInfo(Variant::{variant_type}, "{names[i].strip()}")'
    
    return params_string
        

def generate(src_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    for filename in sorted(os.listdir(src_dir)):
        if not filename.endswith('.h') or filename.endswith('.gen.h'):
            continue

        filepath = os.path.join(src_dir, filename)
        result = parse_header(filepath)
        if not result:
            continue

        class_name, parent_name, properties, functions, signals = result
        base_name = os.path.splitext(filename)[0]

        # Auto-insert the gen.h include into the source file if missing
        ensure_gen_include(filepath, base_name)

        # ------------------------------------------------------------------ #
        # Write .gen.h — redefines GD_GENERATED_BODY() for this specific class
        # NO #pragma once — must stay re-includable so the macro can be overridden
        # ------------------------------------------------------------------ #
        macro_lines = [
            f'    GDCLASS({class_name}, {parent_name})',
            'protected:',
            '    static void _bind_methods();',
        ]
        if properties:
            macro_lines.append('public:')
            for cpp_type, prop_name in properties:
                macro_lines.append(f'    {cpp_type} get_{prop_name}() const;')
                macro_lines.append(f'    void set_{prop_name}({cpp_type} val);')

        macro_body = ' \\\n'.join(macro_lines)

        gen_h_content = (
            f'// AUTO-GENERATED by tools/gdheader_gen.py — do not edit\n'
            f'#undef GD_GENERATED_BODY\n'
            f'#define GD_GENERATED_BODY() \\\n'
            f'{macro_body}\n'
        )

        with open(os.path.join(out_dir, f'{base_name}.gen.h'), 'w', encoding='utf-8') as f:
            f.write(gen_h_content)

        # ------------------------------------------------------------------ #
        # Write .gen.cpp — implementations + _bind_methods + registration
        # ------------------------------------------------------------------ #
        lines_cpp = [
            f'// AUTO-GENERATED by tools/gdheader_gen.py — do not edit\n',
            f'#include "../{filename}"\n',
            f'#include "../internal/class_registry.h"\n',
            f'\n',
            f'using namespace godot;\n',
            f'\n',
        ]

        for cpp_type, prop_name in properties:
            lines_cpp.append(f'{cpp_type} {class_name}::get_{prop_name}() const {{ return {prop_name}; }}\n')
            lines_cpp.append(f'void {class_name}::set_{prop_name}({cpp_type} val) {{ {prop_name} = val; }}\n')

        if properties:
            lines_cpp.append('\n')

        lines_cpp.append(f'void {class_name}::_bind_methods() {{\n')
        for cpp_type, prop_name in properties:
            variant_type = TYPE_MAP.get(cpp_type, 'NIL')
            lines_cpp.append(f'    ClassDB::bind_method(D_METHOD("get_{prop_name}"), &{class_name}::get_{prop_name});\n')
            lines_cpp.append(f'    ClassDB::bind_method(D_METHOD("set_{prop_name}", "{prop_name}"), &{class_name}::set_{prop_name});\n')
            lines_cpp.append(f'    ADD_PROPERTY(PropertyInfo(Variant::{variant_type}, "{prop_name}"), "set_{prop_name}", "get_{prop_name}");\n')

        for signal_name, signal_parameters in signals:
            lines_cpp.append(f'    ADD_SIGNAL(MethodInfo("{signal_name}"{build_signal_params_string(signal_parameters)}));\n')
        
        for _, method_name, parameters in functions:
            lines_cpp.append(f'    ClassDB::bind_method(D_METHOD("{method_name}"{build_method_params_string(parameters)}), &{class_name}::{method_name});\n')
        
        lines_cpp.append('}\n\n')

        lines_cpp.append(
            f'namespace {{\n'
            f'    bool _registered_{class_name} = []() {{\n'
            f'        godot::ClassRegistry::get().add([]() {{ GDREGISTER_CLASS({class_name}); }});\n'
            f'        return true;\n'
            f'    }}();\n'
            f'}}\n'
        )

        with open(os.path.join(out_dir, f'{base_name}.gen.cpp'), 'w', encoding='utf-8') as f:
            f.writelines(lines_cpp)

        props_info = f'{len(properties)} propert{"y" if len(properties) == 1 else "ies"}' if properties else 'no properties'
        print(f'[gdheader_gen] {class_name} ({props_info}) -> {base_name}.gen.h / .gen.cpp')


if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(script_dir, '..', 'src')
    out_dir = os.path.join(src_dir, 'generated')
    generate(src_dir, out_dir)
