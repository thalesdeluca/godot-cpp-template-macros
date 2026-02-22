#pragma once

#define GDPROPERTY() // exposes and binds the property to be accessible within godot
#define GDFUNCTION() // exposes and binds the method to be accessible within godot
#define GDSIGNAL(signal_name, ...) // export new signal
#define GD_GENERATED_BODY() // adds boilerplate bind_methods, GDCLASS and setters/getters