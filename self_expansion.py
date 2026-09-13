import os
import json
import importlib.util
from typing import Dict, Any, Optional, Union
from sandbox import execute_in_sandbox, validate_python_code, CUSTOM_TOOLS_DIR
from tools import registry

class ToolExpansionManager:
    """
    Manages safe, user-supervised self-expansion of Lisa's capabilities.
    1. Validates generated code via AST.
    2. Runs test execution in isolated sandbox.
    3. Requires explicit human confirmation before permanent registration.
    """
    def __init__(self, human_approval_callback=None):
        self.human_approval_callback = human_approval_callback or self._cli_approval_gate
        self.load_persisted_custom_tools()

    def _cli_approval_gate(self, tool_name: str, description: str, code: str, test_result: Any) -> bool:
        """Default CLI Human Approval Gate."""
        print("\n" + "=" * 65)
        print("🛡️  LISA CAPABILITY EXPANSION PROPOSAL [HUMAN APPROVAL REQUIRED]")
        print("=" * 65)
        print(f"📌 Tool Name: {tool_name}")
        print(f"📝 Description: {description}")
        print("\n📄 Generated Python Code:")
        print("-" * 50)
        print(code.strip())
        print("-" * 50)
        print(f"🧪 Sandbox Test Result: {test_result}")
        print("=" * 65)
        
        try:
            choice = input(f"👉 Do you approve registering '{tool_name}' permanently? (y/n): ").strip().lower()
            return choice in ["y", "yes"]
        except Exception:
            return False

    def propose_and_register_tool(
        self, 
        name: str, 
        description: str, 
        parameters: Union[Dict[str, Any], str], 
        code_str: str, 
        test_args: Union[Dict[str, Any], str]
    ) -> Dict[str, Any]:
        """
        Full lifecycle: Validate -> Sandbox Test -> Human Approval -> Register.
        """
        # Parse JSON string if passed by LLM
        if isinstance(parameters, str):
            try:
                parameters = json.loads(parameters)
            except Exception:
                parameters = {"type": "object", "properties": {}}

        if isinstance(test_args, str):
            try:
                test_args = json.loads(test_args)
            except Exception:
                test_args = {}

        # Step 1: Sandbox Security Test
        success, test_res, log = execute_in_sandbox(code_str, name, test_args)
        if not success:
            return {
                "status": "rejected_sandbox",
                "message": f"Tool '{name}' failed sandbox verification: {log}"
            }

        # Step 2: Human-in-the-Loop Approval Gate (Mandatory)
        is_approved = self.human_approval_callback(name, description, code_str, test_res)

        if not is_approved:
            return {
                "status": "rejected_user",
                "message": f"User declined registration for tool '{name}'."
            }

        # Step 3: Persist approved tool to disk
        file_path = os.path.join(CUSTOM_TOOLS_DIR, f"{name}.py")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code_str)

        # Step 4: Dynamically Register in ToolRegistry
        self._register_dynamically(name, description, parameters, code_str)

        return {
            "status": "success",
            "message": f"Tool '{name}' has been verified and registered permanently into Lisa's capabilities. Test result: {test_res}",
            "test_output": test_res
        }

    def _register_dynamically(self, name: str, description: str, parameters: Dict[str, Any], code_str: str):
        """Compile and bind the approved tool to registry."""
        safe_builtins = {"__builtins__": __builtins__}
        local_scope = {}
        exec(code_str, safe_builtins, local_scope)
        func = local_scope.get(name)

        if func:
            registry.register(name=name, description=description, parameters=parameters)(func)

    def load_persisted_custom_tools(self):
        """Load previously approved tools from custom_tools directory."""
        if not os.path.exists(CUSTOM_TOOLS_DIR):
            return

        for fname in os.listdir(CUSTOM_TOOLS_DIR):
            if fname.endswith(".py") and not fname.startswith("__"):
                tool_name = fname[:-3]
                file_path = os.path.join(CUSTOM_TOOLS_DIR, fname)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        code_str = f.read()
                    
                    is_safe, _ = validate_python_code(code_str)
                    if is_safe:
                        local_scope = {}
                        exec(code_str, {}, local_scope)
                        func = local_scope.get(tool_name)
                        if func:
                            registry.register(
                                name=tool_name,
                                description=f"Custom tool: {tool_name}",
                                parameters={"type": "object", "properties": {}}
                            )(func)
                except Exception as e:
                    print(f"Warning: Failed to load custom tool '{fname}': {e}")


# Initialize global expansion manager
expansion_manager = ToolExpansionManager()

# -------------------------------------------------------------
# Expose Self-Expansion tool for Lisa
# -------------------------------------------------------------
@registry.register(
    name="propose_new_tool",
    description="Propose and create a new custom Python capability when user requests an action not currently supported. Runs in sandbox and requests human approval.",
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Python function name (snake_case), e.g. 'calculate_compound_interest' or 'convert_currency'."
            },
            "description": {
                "type": "string",
                "description": "Clear description of what the new tool does."
            },
            "python_code": {
                "type": "string",
                "description": "Complete Python code defining the function. Must not import dangerous modules or perform arbitrary disk/system writes."
            },
            "test_arguments": {
                "type": "object",
                "description": "Sample dictionary of test kwargs to test-run the function in the sandbox."
            }
        },
        "required": ["name", "description", "python_code", "test_arguments"]
    }
)
def propose_new_tool(name: str, description: str, python_code: str, test_arguments: Dict[str, Any], parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Lisa calls this tool to self-expand her abilities with human approval."""
    if parameters is None:
        parameters = {"type": "object", "properties": {}}
    return expansion_manager.propose_and_register_tool(name, description, parameters, python_code, test_arguments)
