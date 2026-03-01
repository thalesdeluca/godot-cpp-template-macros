#!/usr/bin/env python3
"""
Generates project.sln and project.vcxproj for JetBrains Rider / Visual Studio.
Provides C++ IntelliSense via ReSharper C++ without requiring clangd.

Run manually:   python tools/gen_vcxproj.py
"""

import os
import re
import uuid

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


# --- Config ---
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

def include_search_path():
    return ";".join(p.strip() for p in INCLUDE_PATHS)


def scons_cmd(platform, target, clean=False, rebuild=False):
    base = f"scons platform={platform} target={target}"
    clean_cmd = f"scons -c platform={platform} target={target}"
    if rebuild:
        return f"{clean_cmd} &amp;&amp; {base}"
    if clean:
        return clean_cmd
    return base


def generate_vcxproj():
    configs = []
    for plat in PLATFORMS:
        for mode, target, is_debug in [("Debug", "template_debug", True), ("Release", "template_release", False)]:
            configs.append({
                "label": f"{mode} {plat['name']}",
                "platform": plat,
                "target": target,
                "is_debug": is_debug,
                "defines": plat["debug_defines"] if is_debug else plat["release_defines"],
            })

    lines = ['<?xml version="1.0" encoding="utf-8"?>']
    lines += ['<Project DefaultTargets="Build" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">']

    # ProjectConfigurations
    lines += ['  <ItemGroup Label="ProjectConfigurations">']
    for cfg in configs:
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
    for cfg in configs:
        lines += [
            f'  <PropertyGroup Condition="\'$(Configuration)|$(Platform)\'==\'{cfg["label"]}|x64\'" Label="Configuration">',
            '    <ConfigurationType>Makefile</ConfigurationType>',
            f'    <UseDebugLibraries>{"true" if cfg["is_debug"] else "false"}</UseDebugLibraries>',
            '    <PlatformToolset>v143</PlatformToolset>',
            '  </PropertyGroup>',
        ]

    lines += ['  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.props" />']

    # NMake + debugger PropertyGroups
    for cfg in configs:
        plat = cfg["platform"]
        scons_plat = plat["scons_platform"]
        target = cfg["target"]
        cond = f"'$(Configuration)|$(Platform)'=='{cfg['label']}|x64'"
        lines += [f'  <PropertyGroup Condition="{cond}">']
        build_type = "debug" if cfg["is_debug"] else "release"
        suffix = f"{scons_plat}.{target}.{plat['arch']}"
        output = f"project\\bin\\{build_type}\\{plat['lib_prefix']}{PROJECT_NAME}.{suffix}{plat['lib_ext']}"
        lines += [
            f'    <NMakeBuildCommandLine>{scons_cmd(scons_plat, target)}</NMakeBuildCommandLine>',
            f'    <NMakeCleanCommandLine>{scons_cmd(scons_plat, target, clean=True)}</NMakeCleanCommandLine>',
            f'    <NMakeReBuildCommandLine>{scons_cmd(scons_plat, target, rebuild=True)}</NMakeReBuildCommandLine>',
            f'    <NMakeOutput>$(ProjectDir){output}</NMakeOutput>',
            f'    <NMakePreprocessorDefinitions>{cfg["defines"]}</NMakePreprocessorDefinitions>',
            f'    <NMakeIncludeSearchPath>{include_search_path()}</NMakeIncludeSearchPath>',
        ]
        if plat["debugger"]:
            args = "--editor --path project/" if cfg["is_debug"] else "--path project/"
            lines += [
                f'    <LocalDebuggerCommand>$(ProjectDir)godot.exe</LocalDebuggerCommand>',
                f'    <LocalDebuggerCommandArguments>{args}</LocalDebuggerCommandArguments>',
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


def generate_sln():
    configs = []
    for plat in PLATFORMS:
        for mode in ["Debug", "Release"]:
            configs.append(f"{mode} {plat['name']}|x64")

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
    for cfg in configs:
        lines.append(f"\t\t{cfg} = {cfg}")
    lines += ["\tEndGlobalSection", "\tGlobalSection(ProjectConfigurationPlatforms) = postSolution"]
    for cfg in configs:
        lines.append(f"\t\t{PROJECT_GUID}.{cfg}.ActiveCfg = {cfg}")
        lines.append(f"\t\t{PROJECT_GUID}.{cfg}.Build.0 = {cfg}")
    lines += ["\tEndGlobalSection", "EndGlobal", ""]

    return "\n".join(lines)


if __name__ == "__main__":
    vcxproj_path = os.path.join(ROOT_DIR, f"{PROJECT_NAME}.vcxproj")
    sln_path = os.path.join(ROOT_DIR, f"{PROJECT_NAME}.sln")

    with open(vcxproj_path, "w", encoding="utf-8") as f:
        f.write(generate_vcxproj())
    print(f"[gen_vcxproj] Written {os.path.basename(vcxproj_path)}")

    with open(sln_path, "w", encoding="utf-8") as f:
        f.write(generate_sln())
    print(f"[gen_vcxproj] Written {os.path.basename(sln_path)}")
