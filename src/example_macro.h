#pragma once

#include "internal/stubs.h"
#include <godot_cpp/classes/node.hpp>
#include "generated/example_macro.gen.h"

namespace godot {
    class Camera3D;

    class ExampleMacro : public Node {
        GD_GENERATED_BODY()
        GDSIGNAL("test_signal", float, param1, int, param2)

    private:
        GDPROPERTY()
        float speed;

        GDPROPERTY()
        Camera3D* camera;

    public:
        GDFUNCTION()
        int calculate_test(int test1, int test2, int test3);

        GDFUNCTION()
        void ready();

        GDFUNCTION()
        void ready_editor();
    };
}
