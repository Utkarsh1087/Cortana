import sys
from llm import get_llm_provider
from memory import get_memory_manager
from tools import registry
import self_expansion

def main():
    print("=" * 60)
    print("✨ Lisa - Personal AI Voice Assistant ✨")
    print("=" * 60)
    print("Initializing Lisa's brain, memory & capabilities...", end="", flush=True)
    
    try:
        provider = get_llm_provider()
        memory = get_memory_manager("sqlite")
        print(" Ready.")
        print(f"✓ Connected ({len(registry.tools)} active tools loaded).")
    except Exception as e:
        print(f"\n❌ Error during initialization: {e}")
        sys.exit(1)
        
    print("-" * 60)
    
    # Generate & Display Lisa's startup greeting
    try:
        context_messages = memory.get_recent_context(limit=6)
        greeting_prompt = context_messages + [{"role": "user", "content": "Hello Lisa, you just came online. Give a short, natural greeting."}]
        initial_greeting = provider.generate_response(greeting_prompt, tool_registry=registry)
    except Exception:
        initial_greeting = "Hey sweetie! I'm online and ready. What's on your mind today?"
        
    print(f"Lisa: {initial_greeting}\n")
    print("Commands: 'clear memory' to reset history | 'exit' to quit.\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ["exit", "quit", "q"]:
                print("\nLisa: Goodbye for now. Let me know when you need me next.")
                break

            if user_input.lower() == "clear memory":
                memory.clear_memory()
                print("Lisa: I have cleared our conversation history.\n")
                continue
                
            # 1. Save user turn to persistent memory
            memory.add_interaction("user", user_input)
            
            # 2. Retrieve recent context history from persistent memory
            context_messages = memory.get_recent_context(limit=10)
            
            print("⏳ Lisa is thinking...", end="\r", flush=True)
            response = provider.generate_response(context_messages, tool_registry=registry)
            # Clear the thinking line cleanly
            sys.stdout.write("\r" + " " * 35 + "\r")
            sys.stdout.flush()
            
            # Print response
            print(f"Lisa: {response}\n")
            
            # 3. Save assistant turn to persistent memory
            memory.add_interaction("assistant", response)
            
        except KeyboardInterrupt:
            print("\n\nLisa: Session closed. Have a wonderful day!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")

if __name__ == "__main__":
    main()
