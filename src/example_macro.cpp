#include "example_macro.h"
#include "godot_cpp/classes/camera3d.hpp"

using namespace godot;

int ExampleMacro::calculate_test(int test1, int test2, int test3)
{
    emit_signal("test_signal", 2, 3);
    return 0;
}

void ExampleMacro::ready()
{
    UtilityFunctions::print("I run only on runtime");
}

void ExampleMacro::ready_editor()
{
    UtilityFunctions::print("I run only on editor");
}
