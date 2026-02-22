#pragma once

#include "internal/stubs.h"
#include <godot_cpp/classes/node.hpp>
#include "generated/example.gen.h"

namespace godot {
    class Example : public Node {
        GD_GENERATED_BODY()
        GDSIGNAL("test_signal", float, param1, int, param2)

    private:
        GDPROPERTY()
        float speed;

    public:
        GDFUNCTION()
        int calculate_test(int test1, int test2, int test3);
    };
}
