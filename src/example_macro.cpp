#include "example_macro.h"

using namespace godot;

int ExampleMacro::calculate_test(int test1, int test2, int test3)
{
    emit_signal("test_signal", 2, 3);
    return 0;
}