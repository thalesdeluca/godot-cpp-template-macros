#!/usr/bin/env python3
"""
Generates project.sln, project.vcxproj, and .run/*.run.xml for JetBrains Rider.
Provides C++ IntelliSense via ReSharper C++ without requiring clangd.

Run manually:   python tools/gen_vcxproj.py

Workflow in Rider:
  1. Pick a BUILD config ("Debug Windows", "Release Windows", …)
  2. Pick a RUN config  ("Windows Editor", "Windows Game", …)
  3. Press Play or Debug
"""

import os
import re

ROOT_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))


def detect_project_name():
    """Read project_name from SConstruct, fall back to folder name."""
    sconstruct = os.path.join(ROOT_DIR, "SConstruct")
    if os.path.exists(sconstruct):
        with open(sconstruct, encoding="utf-8") as f:
            m = re.search(r'^project_name\s*=\s*["\'](\w+)["\']', f.read(), re.MULTILINE)
            if m:
                return m.group(1)
    return os.path.basename(ROOT_DIR).lower()


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PROJECT_NAME = detect_project_name()
PROJECT_GUID = "{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}"

INCLUDE_PATHS = [
    r"$(ProjectDir)src\ ",
    r"$(ProjectDir)godot-cpp\include\ ",
    r"$(ProjectDir)godot-cpp\gdextension\ ",
    r"$(ProjectDir)godot-cpp\gen\include\ ",
]

PLATFORMS = [
    {
        "name": "Windows",
        "scons_platform": "windows",
        "arch": "x86_64",
        "lib_prefix": "",
        "lib_ext": ".dll",
        "debugger": True,
        "debug_defines": "_DEBUG;UNICODE;_UNICODE;TOOLS_ENABLED",
        "release_defines": "UNICODE;_UNICODE",
    },
    {
        "name": "Linux",
        "scons_platform": "linux",
        "arch": "x86_64",
        "lib_prefix": "lib",
        "lib_ext": ".so",
        "debugger": False,
        "debug_defines": "_DEBUG;TOOLS_ENABLED",
        "release_defines": "",
    },
    {
        "name": "Android",
        "scons_platform": "android",
        "arch": "arm64",
        "lib_prefix": "lib",
        "lib_ext": ".so",
        "debugger": False,
        "debug_defines": "_DEBUG;TOOLS_ENABLED",
        "release_defines": "",
    },
]


# ---------------------------------------------------------------------------
# Build configurations  (one entry = one <ProjectConfiguration> in vcxproj)
# ---------------------------------------------------------------------------
def make_build_configs():
    configs = []
    for plat in PLATFORMS:
        for mode, target, is_debug in [
            ("Debug", "template_debug", True),
            ("Release", "template_release", False),
        ]:
            configs.append({
                "label": f"{mode} {plat['name']}",
                "platform": plat,
                "target": target,
                "is_debug": is_debug,
                "defines": plat["debug_defines"] if is_debug else plat["release_defines"],
            })
    return configs


# ---------------------------------------------------------------------------
# Run configurations  (one entry = one .run.xml file)
# ---------------------------------------------------------------------------
def make_run_configs():
    run_cfgs = []

    # Add a clean build config (no platform-specific, runs scons -c)
    run_cfgs.append({
        "label": "Clean Build",
        "is_clean": True,
        "platform": None,
    })

    for plat in PLATFORMS:
        if plat["name"] == "Windows":
            # Two launch modes for the debug build
            run_cfgs.append({
                "label": "Windows Editor",
                "build_label": "Debug Windows",
                "platform": plat,
                "launch_args": "--editor --path project/",
            })
            run_cfgs.append({
                "label": "Windows Game",
                "build_label": "Debug Windows",
                "platform": plat,
                "launch_args": "--path project/",
            })
            run_cfgs.append({
                "label": "Release Windows",
                "build_label": "Release Windows",
                "platform": plat,
                "launch_args": "--path project/",
            })
        else:
            for mode in ("Debug", "Release"):
                label = f"{mode} {plat['name']}"
                run_cfgs.append({
                    "label": label,
                    "build_label": label,
                    "platform": plat,
                    "launch_args": "--path project/",
                })
    return run_cfgs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def scons_cmd(platform, target, clean=False, rebuild=False, extra_flags=""):
    flags = f" {extra_flags}" if extra_flags else ""
    base = f"scons platform={platform} target={target}{flags}"
    clean_cmd = f"scons -c platform={platform} target={target}"
    if rebuild:
        return f"{clean_cmd} &amp;&amp; {base}"
    if clean:
        return clean_cmd
    return base


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------
def generate_vcxproj(build_configs):
    lines = ['<?xml version="1.0" encoding="utf-8"?>']
    lines += ['<Project DefaultTargets="Build" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">']

    # ProjectConfigurations
    lines += ['  <ItemGroup Label="ProjectConfigurations">']
    for cfg in build_configs:
        lines += [
            f'    <ProjectConfiguration Include="{cfg["label"]}|x64">',
            f'      <Configuration>{cfg["label"]}</Configuration>',
            f'      <Platform>x64</Platform>',
            f'    </ProjectConfiguration>',
        ]
    lines += ['  </ItemGroup>']

    # Globals
    lines += [
        '  <PropertyGroup Label="Globals">',
        '    <VCProjectVersion>16.0</VCProjectVersion>',
        '    <Keyword>MakeFileProj</Keyword>',
        f'    <ProjectGuid>{PROJECT_GUID}</ProjectGuid>',
        f'    <RootNamespace>{PROJECT_NAME}</RootNamespace>',
        '  </PropertyGroup>',
        '  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.Default.props" />',
    ]

    # Configuration label PropertyGroups
    for cfg in build_configs:
        lines += [
            f'  <PropertyGroup Condition="\'$(Configuration)|$(Platform)\'==\'{cfg["label"]}|x64\'" Label="Configuration">',
            '    <ConfigurationType>Makefile</ConfigurationType>',
            f'    <UseDebugLibraries>{"true" if cfg["is_debug"] else "false"}</UseDebugLibraries>',
            '    <PlatformToolset>v143</PlatformToolset>',
            '  </PropertyGroup>',
        ]

    lines += ['  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.props" />']
    lines += [
        '  <PropertyGroup>',
        '    <DisableFastUpToDateCheck>true</DisableFastUpToDateCheck>',
        '  </PropertyGroup>',
    ]

    # NMake + debugger PropertyGroups
    for cfg in build_configs:
        plat = cfg["platform"]
        scons_plat = plat["scons_platform"]
        target = cfg["target"]
        cond = f"'$(Configuration)|$(Platform)'=='{cfg['label']}|x64'"
        build_type = "debug" if cfg["is_debug"] else "release"
        suffix = f"{scons_plat}.{target}.{plat['arch']}"
        dll_output = f"project\\bin\\{build_type}\\{plat['lib_prefix']}{PROJECT_NAME}.{suffix}{plat['lib_ext']}"
        extra = "debug_symbols=yes optimize=none" if cfg["is_debug"] and plat["debugger"] else ""

        # Rider reads NMakeOutput to determine the launch executable.
        # Point Windows builds at godot.exe so Rider never tries to execute the DLL.
        nmake_output = "$(ProjectDir)godot.exe" if plat["debugger"] else f"$(ProjectDir){dll_output}"

        lines += [f'  <PropertyGroup Condition="{cond}">']
        lines += [
            f'    <NMakeBuildCommandLine>{scons_cmd(scons_plat, target, extra_flags=extra)}</NMakeBuildCommandLine>',
            f'    <NMakeCleanCommandLine>{scons_cmd(scons_plat, target, clean=True)}</NMakeCleanCommandLine>',
            f'    <NMakeReBuildCommandLine>{scons_cmd(scons_plat, target, rebuild=True, extra_flags=extra)}</NMakeReBuildCommandLine>',
            f'    <NMakeOutput>{nmake_output}</NMakeOutput>',
            f'    <NMakePreprocessorDefinitions>{cfg["defines"]}</NMakePreprocessorDefinitions>',
            f'    <NMakeIncludeSearchPath>{";".join(p.strip() for p in INCLUDE_PATHS)}</NMakeIncludeSearchPath>',
        ]
        if plat["debugger"]:
            # LocalDebuggerCommand is left intentionally without args so that
            # PROGRAM_PARAMETERS in each individual run.xml file is the
            # authoritative source for editor vs game launch mode.
            lines += [
                f'    <LocalDebuggerCommand>$(ProjectDir)godot.exe</LocalDebuggerCommand>',
                f'    <LocalDebuggerCommandArguments></LocalDebuggerCommandArguments>',
                f'    <LocalDebuggerWorkingDirectory>$(ProjectDir)</LocalDebuggerWorkingDirectory>',
                f'    <DebuggerFlavor>WindowsLocalDebugger</DebuggerFlavor>',
            ]
        lines += ['  </PropertyGroup>']

    # Source files (wildcards — auto-picks up new files)
    lines += [
        '  <ItemGroup>',
        r'    <ClCompile Include="src\**\*.cpp" />',
        '  </ItemGroup>',
        '  <ItemGroup>',
        r'    <ClInclude Include="src\**\*.h" />',
        '  </ItemGroup>',
        '  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.targets" />',
        '</Project>',
    ]
    return "\n".join(lines) + "\n"


def _run_xml_block(i, build_cfg, launch_args):
    """One <configuration_N> block inside a run.xml."""
    plat = build_cfg["platform"]
    lines = [f'    <configuration_{i}>']
    lines += [f'      <option name="CONFIGURATION" value="{build_cfg["label"]}" />']
    lines += [f'      <option name="PLATFORM" value="x64" />']
    lines += [f'      <option name="PROJECT_FILE_PATH" value="$PROJECT_DIR$/{PROJECT_NAME}.vcxproj" />']
    lines += [f'      <option name="CURRENT_LAUNCH_PROFILE" value="Local" />']
    if plat["debugger"]:
        lines += [f'      <option name="EXE_PATH" value="$PROJECT_DIR$/godot.exe" />']
        lines += [f'      <option name="PROGRAM_PARAMETERS" value="{launch_args}" />']
        lines += [f'      <option name="WORKING_DIRECTORY" value="$PROJECT_DIR$" />']
    else:
        lines += [f'      <option name="EXE_PATH" value="$(LocalDebuggerCommand)" />']
        lines += [f'      <option name="PROGRAM_PARAMETERS" value="$(LocalDebuggerCommandArguments)" />']
        lines += [f'      <option name="WORKING_DIRECTORY" value="$(LocalDebuggerWorkingDirectory)" />']
    lines += [f'      <option name="PASS_PARENT_ENVS" value="1" />']
    lines += [f'      <option name="USE_EXTERNAL_CONSOLE" value="0" />']
    lines += [f'    </configuration_{i}>']
    return lines


def generate_clean_run_xml(run_cfg):
    """Generate a clean build run.xml (special case, not tied to build configs)."""
    lines = ['<component name="ProjectRunConfigurationManager">']
    lines += [f'  <configuration default="false" name="{run_cfg["label"]}" type="ShConfigurationType">']
    lines += ['    <option name="SCRIPT_TEXT" value="scons -c" />']
    lines += ['    <option name="INDEPENDENT_SCRIPT_PATH" value="false" />']
    lines += ['    <option name="SCRIPT_PATH" value="" />']
    lines += ['    <option name="SCRIPT_OPTIONS" value="" />']
    lines += ['    <option name="INDEPENDENT_SCRIPT_WORKING_DIRECTORY" value="true" />']
    lines += ['    <option name="SCRIPT_WORKING_DIRECTORY" value="$PROJECT_DIR$" />']
    lines += ['    <option name="INDEPENDENT_INTERPRETER_PATH" value="true" />']
    lines += ['    <option name="INTERPRETER_PATH" value="" />']
    lines += ['    <option name="INTERPRETER_OPTIONS" value="" />']
    lines += ['    <option name="EXECUTE_IN_TERMINAL" value="true" />']
    lines += ['    <option name="EXECUTE_SCRIPT_FILE" value="false" />']
    lines += ['    <envs />']
    lines += ['    <method v="2" />']
    lines += ['  </configuration>']
    lines += ['</component>']
    return "\n".join(lines) + "\n"


def generate_run_xml(run_cfg, all_build_configs):
    """Generate a single .run.xml for run_cfg.

    All build configurations are pre-populated (primary first) so Rider never
    back-fills missing entries with $(TargetPath)."""
    label = run_cfg["label"]
    primary_label = run_cfg["build_label"]
    primary_args = run_cfg["launch_args"]

    primary = next(c for c in all_build_configs if c["label"] == primary_label)
    others = [c for c in all_build_configs if c["label"] != primary_label]

    lines = ['<component name="ProjectRunConfigurationManager">']
    lines += [f'  <configuration default="false" name="{label}" type="CppProject" factoryName="C++ Project">']

    for i, build_cfg in enumerate([primary] + others, start=1):
        # Primary gets the run config's specific args; others get a neutral default.
        if build_cfg["label"] == primary_label:
            args = primary_args
        elif build_cfg["platform"]["debugger"]:
            args = "--path project/"
        else:
            args = "$(LocalDebuggerCommandArguments)"
        lines += _run_xml_block(i, build_cfg, args)

    lines += [f'    <option name="DEFAULT_PROJECT_PATH" value="$PROJECT_DIR$/{PROJECT_NAME}.vcxproj" />']
    lines += ['    <method v="2">']
    lines += ['      <option name="Build" projectName="Selected project" />']
    lines += ['    </method>']
    lines += ['  </configuration>']
    lines += ['</component>']
    return "\n".join(lines) + "\n"


def generate_sln(build_configs):
    cfg_labels = [f"{c['label']}|x64" for c in build_configs]
    lines = [
        "",
        "Microsoft Visual Studio Solution File, Format Version 12.00",
        "# Visual Studio Version 17",
        "VisualStudioVersion = 17.0.31903.59",
        "MinimumVisualStudioVersion = 10.0.40219.1",
        f'Project("{{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}}") = "{PROJECT_NAME}", "{PROJECT_NAME}.vcxproj", "{PROJECT_GUID}"',
        "EndProject",
        "Global",
        "\tGlobalSection(SolutionConfigurationPlatforms) = preSolution",
    ]
    for cfg in cfg_labels:
        lines.append(f"\t\t{cfg} = {cfg}")
    lines += ["\tEndGlobalSection", "\tGlobalSection(ProjectConfigurationPlatforms) = postSolution"]
    for cfg in cfg_labels:
        lines.append(f"\t\t{PROJECT_GUID}.{cfg}.ActiveCfg = {cfg}")
        lines.append(f"\t\t{PROJECT_GUID}.{cfg}.Build.0 = {cfg}")
    lines += ["\tEndGlobalSection", "EndGlobal", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    build_configs = make_build_configs()
    run_configs = make_run_configs()

    vcxproj_path = os.path.join(ROOT_DIR, f"{PROJECT_NAME}.vcxproj")
    sln_path = os.path.join(ROOT_DIR, f"{PROJECT_NAME}.sln")
    run_dir = os.path.join(ROOT_DIR, ".run")

    with open(vcxproj_path, "w", encoding="utf-8") as f:
        f.write(generate_vcxproj(build_configs))
    print(f"[gen_vcxproj] Written {os.path.basename(vcxproj_path)}")

    with open(sln_path, "w", encoding="utf-8") as f:
        f.write(generate_sln(build_configs))
    print(f"[gen_vcxproj] Written {os.path.basename(sln_path)}")

    os.makedirs(run_dir, exist_ok=True)
    generated = set()
    for run_cfg in run_configs:
        filename = run_cfg["label"].lower().replace(" ", "-") + ".run.xml"
        path = os.path.join(run_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            # Handle clean build config specially
            if run_cfg.get("is_clean"):
                f.write(generate_clean_run_xml(run_cfg))
            else:
                f.write(generate_run_xml(run_cfg, build_configs))
        generated.add(filename)
        print(f"[gen_vcxproj] Written .run/{filename}")

    for existing in os.listdir(run_dir):
        if existing.endswith(".run.xml") and existing not in generated:
            os.remove(os.path.join(run_dir, existing))
            print(f"[gen_vcxproj] Removed stale .run/{existing}")
