#pragma once
#include <functional>
#include <vector>

namespace godot {
class ClassRegistry {
    public: 
        static ClassRegistry& get() {
            static ClassRegistry instance;
            return instance;
        }
    
        void add(std::function<void()> fn) { registrations_.push_back(fn); }
        void register_all() { for (auto& fn : registrations_) fn(); }
    private:
        std::vector<std::function<void()>> registrations_;
};
}