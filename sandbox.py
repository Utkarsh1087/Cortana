import ast
import os
import sys
import json
import time
import math
import random
import datetime
from typing import Dict, Any, Tuple, Optional

# Designated sandbox directory (no writes outside this directory allowed)
SANDBOX_DIR = os.path.join(os.path.dirname(__file__), "custom_tools_sandbox")
CUSTOM_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "custom_tools")

os.makedirs(SANDBOX_DIR, exist_ok=True)
os.makedirs(CUSTOM_TOOLS_DIR, exist_ok=True)

# Strict Disallowed AST Nodes & Imports
BLOCKED_IMPORTS = {
    "os", "sys", "subprocess", "shutil", "ctypes", "socket", 
    "pickle", "marshal", "pty", "builtins", "__builtin__",
    "importlib", "pathlib"
}

BLOCKED_FUNCTIONS = {
    "eval", "exec", "compile", "open", "input", "__import__",
    "globals", "locals", "getattr", "setattr", "delattr"
}

ALLOWED_MODULES = {
    "math": math,
    "random": random,
    "datetime": datetime,
    "json": json,
    "time": time
}

class SecurityPolicyError(Exception):
    """Raised when code violates security policies."""
    pass


class CodeSandboxValidator(ast.NodeVisitor):
    """
    Performs static AST security analysis on generated code before execution.
    """
    def __init__(self):
        self.errors = []

    def visit_Import(self, node):
        for alias in node.names:
            base_module = alias.name.split('.')[0]
            if base_module in BLOCKED_IMPORTS or base_module not in ALLOWED_MODULES:
                self.errors.append(f"Security Violation: Import of '{alias.name}' is prohibited in sandbox.")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            base_module = node.module.split('.')[0]
            if base_module in BLOCKED_IMPORTS or base_module not in ALLOWED_MODULES:
                self.errors.append(f"Security Violation: Import from '{node.module}' is prohibited in sandbox.")
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            if node.func.id in BLOCKED_FUNCTIONS:
                self.errors.append(f"Security Violation: Call to '{node.func.id}()' is prohibited.")
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if node.attr.startswith("__"):
            self.errors.append(f"Security Violation: Access to dunder attribute '{node.attr}' is prohibited.")
        self.generic_visit(node)


def validate_python_code(code_str: str) -> Tuple[bool, Optional[str]]:
    """
    Statically analyzes code to ensure no dangerous operations or unauthorized system access.
    """
    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        return False, f"Syntax Error in generated code: {str(e)}"

    validator = CodeSandboxValidator()
    validator.visit(tree)

    if validator.errors:
        return False, "\n".join(validator.errors)

    return True, None


def execute_in_sandbox(code_str: str, function_name: str, test_args: Dict[str, Any]) -> Tuple[bool, Any, str]:
    """
    Executes function in a restricted execution namespace with strict scope isolation.
    """
    # 1. Static AST Validation
    is_safe, error_msg = validate_python_code(code_str)
    if not is_safe:
        return False, None, f"Sandbox Validation Failed:\n{error_msg}"

    # 2. Construct Safe Restricted Globals
    safe_builtins = {
        "abs": abs, "all": all, "any": any, "bin": bin, "bool": bool,
        "dict": dict, "divmod": divmod, "enumerate": enumerate, "filter": filter,
        "float": float, "format": format, "int": int, "isinstance": isinstance,
        "len": len, "list": list, "map": map, "max": max, "min": min,
        "pow": pow, "print": print, "range": range, "reversed": reversed,
        "round": round, "set": set, "slice": slice, "sorted": sorted,
        "str": str, "sum": sum, "tuple": tuple, "type": type, "zip": zip,
        "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError
    }

    safe_globals = {
        "__builtins__": safe_builtins,
        "math": math,
        "random": random,
        "datetime": datetime,
        "json": json
    }

    safe_locals = {}

    try:
        # 3. Compile and load function in sandboxed namespace
        compiled = compile(code_str, "<sandbox>", "exec")
        exec(compiled, safe_globals, safe_locals)

        if function_name not in safe_locals:
            return False, None, f"Function '{function_name}' was not defined in the code."

        func = safe_locals[function_name]
        
        # 4. Execute with test arguments
        result = func(**test_args)
        return True, result, "Execution successful."

    except Exception as e:
        return False, None, f"Runtime error during sandbox execution: {type(e).__name__}: {str(e)}"
