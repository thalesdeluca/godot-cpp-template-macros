# Godot C++ Template with Macros

A streamlined **GDExtension template** for Godot C++ development that reduces boilerplate code through intelligent macros and automatic code generation.

## Overview

This project provides a convenient development template for creating **Godot 4.x GDExtensions** in C++. Instead of manually writing repetitive binding code, you annotate your classes with simple macros, and an automatic code generator creates all the necessary boilerplate for you.

### Key Benefits

- **Less Boilerplate**: Declare properties, methods, and signals with simple macros
- **Automatic Code Generation**: Python script generates binding code automatically
- **Directory Structure Preserved**: Subdirectories in `src/` are preserved in generated files
- **Recursive Compilation**: Automatically finds and compiles `.cpp` files from all subdirectories
- **Single Entry Point**: Classes auto-register without explicit registration calls

## Macros

The template provides four main macros to simplify GDExtension development:

### `GD_GENERATED_BODY()`

Replaces the boilerplate needed inside a Godot class definition. It automatically generates:
- `GDCLASS()` declaration (registers the class with Godot)
- `_bind_methods()` static method (for binding properties and methods)
- Getter and setter declarations for all `GDPROPERTY()` fields

```cpp
class MyClass : public Node {
    GD_GENERATED_BODY()  // ← Replaces ~15 lines of boilerplate
};
```

### `GDPROPERTY()`

Exposes a member variable as a **property** in the Godot editor. The generator automatically creates getter/setter methods and property registration.

```cpp
GDPROPERTY()
float speed;

GDPROPERTY()
String class_name;
```

Supported types:
- `float`, `double` → Godot `FLOAT`
- `int` → Godot `INT`
- `bool` → Godot `BOOL`
- `String` → Godot `STRING`
- `Vector2`, `Vector3` → Godot `VECTOR2`, `VECTOR3`
- `Color` → Godot `COLOR`

### `GDFUNCTION()`

Marks a **method** to be exposed to Godot (callable from GDScript and the editor).

```cpp
GDFUNCTION()
int calculate(int a, int b);

GDFUNCTION()
void apply_effect(Vector3 position);
```

### `GDSIGNAL()`

Declares a **signal** that can be emitted and connected to from GDScript.

```cpp
GDSIGNAL("player_spawned", Vector3, spawn_position, int, player_id)

GDSIGNAL("health_changed", float, new_health)
```

Signal syntax: `GDSIGNAL("signal_name", Type1, param1, Type2, param2, ...)`

## Quick Start

### 1. Create a New Class

Create a header file in `src/` (e.g., `src/my_plugin.h`):

```cpp
#pragma once

#include "internal/stubs.h"
#include <godot_cpp/classes/node.hpp>
#include "generated/my_plugin.gen.h"

namespace godot {
    class MyPlugin : public Node {
        GD_GENERATED_BODY()
        GDSIGNAL("ready")

    private:
        GDPROPERTY()
        float max_speed;

    public:
        GDFUNCTION()
        void initialize();

        GDFUNCTION()
        int get_count();
    };
}
```

Create the implementation file (`src/my_plugin.cpp`):

```cpp
#include "my_plugin.h"

using namespace godot;

void MyPlugin::initialize() {
    emit_signal("ready");
}

int MyPlugin::get_count() {
    return 42;
}
```

### 2. Build

The build system automatically handles everything:

```bash
# Build for the current platform
scons target=template_release
scons target=template_debug

# The generator runs automatically on every build
# It scans src/ and generates src/generated/ files
```

The generated `.gen.h` and `.gen.cpp` files:
- Are automatically created in `src/generated/`
- Contain getter/setter implementations
- Include property and signal registration
- Should NOT be edited manually

### 3. Use in Godot

Your class is now available in Godot:
- **In the editor**: Drag the generated `.gdextension` file into your project
- **In GDScript**: Use your class like any other node

```gdscript
var plugin = MyPlugin.new()
plugin.max_speed = 100.0
plugin.initialize()
plugin.ready.connect(func(): print("Ready!"))
```

## Project Structure

```
godot-cpp-template-macros/
├── src/                          # Your source files
│   ├── example_macro.h
│   ├── example_macro.cpp
│   ├── generated/               # AUTO-GENERATED (do not edit)
│   │   ├── example_macro.gen.h
│   │   └── example_macro.gen.cpp
│   └── internal/
│       ├── stubs.h             # Macro definitions
│       ├── class_registry.h    # Class auto-registration
│       ├── register_types.h    # Godot entry point
│       └── register_types.cpp
├── tools/
│   └── gdheader_gen.py         # Code generator (runs automatically)
├── godot-cpp/                   # Godot C++ bindings (submodule)
├── project/                     # Godot project files
├── SConstruct                   # Build configuration
└── out/                         # Build outputs
```

## How It Works

### Code Generation Process

1. **Build starts**: `SConstruct` runs the generator before compilation
2. **Scanner**: `gdheader_gen.py` recursively scans `src/` for `.h` files
3. **Parser**: Extracts class names, properties, methods, and signals using regex
4. **Generator**: Creates:
   - `.gen.h` files with macro expansions
   - `.gen.cpp` files with implementations
5. **Compilation**: Godot-cpp compiles everything into a GDExtension

### Automatic Class Registration

Classes are registered automatically via a static initializer in the `.gen.cpp` file:

```cpp
namespace {
    bool _registered_MyClass = []() {
        godot::ClassRegistry::get().add([]() { GDREGISTER_CLASS(MyClass); });
        return true;
    }();
}
```

This runs at library load time, before `_enter_tree()` is called.

## Advanced Usage

### Organizing Code in Subdirectories

You can organize your source files in subdirectories, and the generator preserves the structure:

```
src/
├── plugins/
│   ├── audio_plugin.h
│   └── audio_plugin.cpp
└── utils/
    ├── math_utils.h
    └── math_utils.cpp

# Generated files will be:
src/generated/plugins/audio_plugin.gen.h
src/generated/plugins/math_utils.gen.h
# etc.
```

### Manual Property Access

The generated getters and setters are simple pass-through methods. You can override them in your `.cpp` file for custom logic:

```cpp
float MyClass::get_speed() const {
    // The setter auto-generates this, but you can customize it
    return speed * 1.5f; // Apply a multiplier, for example
}
```

## Limitations & Notes

- **Only supported types**: The generator knows about float, int, bool, String, Vector2, Vector3, and Color. Other types default to `Variant::NIL`.
- **No nested classes**: The parser doesn't support nested class definitions.
- **Method parameter names**: Required in function declarations for proper binding.
- **Do not edit generated files**: Changes to `.gen.h` and `.gen.cpp` will be overwritten on the next build.

## Building for Different Platforms

```bash
# Linux
scons platform=linuxbsd target=template_release

# macOS
scons platform=macos target=template_release

# Windows
scons platform=windows target=template_release

# Web (Emscripten)
scons platform=web target=template_release
```

## Visual Studio Code Setup

For a better development experience in VS Code, create the following configuration files:

### `.vscode/tasks.json`

```json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Build Debug",
            "type": "shell",
            "command": "scons",
            "args": ["target=template_debug"],
            "group": {
                "kind": "build",
                "isDefault": true
            },
            "problemMatcher": []
        },
        {
            "label": "Build Release",
            "type": "shell",
            "command": "scons",
            "args": ["target=template_release"],
            "group": "build",
            "problemMatcher": []
        },
        {
            "label": "Generate Code",
            "type": "shell",
            "command": "python",
            "args": ["tools/gdheader_gen.py"],
            "group": "build",
            "problemMatcher": []
        },
        {
            "label": "Clean Build",
            "type": "shell",
            "command": "scons",
            "args": ["-c"],
            "group": "build",
            "problemMatcher": []
        }
    ]
}
```

### `.vscode/launch.json`

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Godot Debug",
            "type": "cppdbg",
            "request": "launch",
            "program": "${workspaceFolder}/godot-cpp/bin/godot.exe",
            "args": ["-e"],
            "stopAtEntry": false,
            "cwd": "${workspaceFolder}/project",
            "environment": [],
            "externalConsole": false,
            "MIMode": "gdb",
            "preLaunchTask": "Build Debug",
            "setupCommands": [
                {
                    "description": "Enable pretty-printing for gdb",
                    "text": "-enable-pretty-printing",
                    "ignoreFailures": true
                }
            ]
        }
    ]
}
```

**Tips**:
- Use <kbd>Ctrl+Shift+B</kbd> to run the default build task
- Use <kbd>F5</kbd> to start debugging (requires Godot executable in path)
- Run "Generate Code" task if you modify macro annotations
- Adjust `program` path if Godot is installed elsewhere

### Recommended Extensions

Install the **C++ Child Process Debugger** by Alber Ziegenhagel:
- Search for `C++ Child Process Debugger` in VS Code extensions
- This debugger can attach to child processes, which is useful for debugging GDExtensions that are loaded by the Godot engine
- Alternative: Use `ms-vscode.cpptools` (C/C++ extension) for standard debugging

## Troubleshooting

**Generated files not updated?**
- Run `python tools/gdheader_gen.py` manually to regenerate
- Check that your `.h` file includes `GD_GENERATED_BODY()`

**Build fails with undefined references?**
- Ensure your implementation `.cpp` file exists
- Check that the `.h` file has the correct `#include` for the `.gen.h` file

**Properties not showing in Godot?**
- Verify the type is in the `TYPE_MAP` dictionary in `gdheader_gen.py`
- Ensure you used `GDPROPERTY()` with no arguments
- Rebuild and reimport the `.gdextension` file

## License

This template builds on top of [godot-cpp](https://github.com/godotengine/godot-cpp), which is licensed under the MIT license.

## See Also

- [Godot C++ Documentation](https://docs.godotengine.org/en/stable/tutorials/scripting/gdextension/index.html)
- [Godot-cpp Repository](https://github.com/godotengine/godot-cpp)
- [GDExtension Best Practices](https://docs.godotengine.org/en/stable/tutorials/scripting/gdextension/gdextension_cpp_example.html)
