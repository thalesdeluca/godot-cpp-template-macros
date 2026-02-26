#pragma once

#include <godot_cpp/classes/node.hpp>
#include <godot_cpp/classes/packed_scene.hpp>
#include <godot_cpp/classes/scene_tree.hpp>
#include <godot_cpp/classes/window.hpp>

#define GDPROPERTY() // exposes and binds the property to be accessible within godot
#define GDFUNCTION() // exposes and binds the method to be accessible within godot
#define GDSIGNAL(signal_name, ...) // export new signal
#define GD_GENERATED_BODY() // adds boilerplate bind_methods, GDCLASS and setters/getters
#define RUNTIME_ONLY() if (Engine::get_singleton()->is_editor_hint()) return;
#define EDITOR_ONLY() if (!Engine::get_singleton()->is_editor_hint()) return;

namespace godot {

template<typename T = Node>
static T* instantiate_scene(Node* context, const Ref<PackedScene>& scene) {
    T* instance = Object::cast_to<T>(scene->instantiate());
    context->get_tree()->get_root()->add_child(instance);
    return instance;
}

} // namespace godot