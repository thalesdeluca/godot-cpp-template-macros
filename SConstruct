#!/usr/bin/env python
import os
import sys
import subprocess

# You can find documentation for SCons and SConstruct files at:
# https://scons.org/documentation.html

# Run the header generator before compiling.
# Scans src/ for GDAUTOCLASS/GDPROPERTY annotations and writes src/generated/*.gen.h/.gen.cpp
subprocess.run([sys.executable, "tools/gdheader_gen.py"], check=True)

# This lets SCons know that we're using godot-cpp, from the godot-cpp folder.
env = SConscript("godot-cpp/SConstruct")

# Configures the 'src' directory as a source for header files.
env.Append(CPPPATH=["src/"])

# Build intermediates in a separate (variant) directory so .obj/.o files don't
# pollute `src/`. The sources remain in `src/` (duplicate=0).
# Include platform/architecture in path so different builds don't conflict.
build_dir = "out/{}".format(env["suffix"])
VariantDir(build_dir, "src", duplicate=0)

# Also map the generated sources into the variant directory.
gen_dir = "{}/generated".format(build_dir)
VariantDir(gen_dir, "src/generated", duplicate=0)

# Collects all .cpp files in both the main and generated variant folders.
sources = Glob(f"{build_dir}/*.cpp") + Glob(f"{gen_dir}/*.cpp")

project_name="macros"
# The filename for the dynamic library for this GDExtension.
# $SHLIBPREFIX is a platform specific prefix for the dynamic library ('lib' on Unix, '' on Windows).
# $SHLIBSUFFIX is the platform specific suffix for the dynamic library (for example '.dll' on Windows).
# env["suffix"] includes the build's feature tags (e.g. '.windows.template_debug.x86_64')
# (see https://docs.godotengine.org/en/stable/tutorials/export/feature_tags.html).
# The final path should match a path in the '.gdextension' file.
lib_filename = "{}{}{}{}".format(env.subst('$SHLIBPREFIX'), project_name, env["suffix"], env.subst('$SHLIBSUFFIX'))
build_type = env["suffix"].split("_")[1].split(".")[0]
# Creates a SCons target for the path with our sources.
library = env.SharedLibrary(
    "project/bin/{}/{}".format(build_type, lib_filename),
    source=sources,
)

# Selects the shared library as the default target.
Default(library)
