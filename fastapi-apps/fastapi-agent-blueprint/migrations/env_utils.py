# -*- coding: utf-8 -*-
import importlib
import os
import pkgutil
from pathlib import Path


def create_folder_if_not_exists(folder_path: str):
    """Create folder if it does not exist"""
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print(f"Folder created: {folder_path}")
    else:
        print(f"Folder already exists: {folder_path}")


def load_models():
    """Automatically import all models that inherit from Base across the project."""
    # Path to the src directory at the project root
    project_root = Path(__file__).parent.parent
    src_path = project_root / "src"
    
    if not src_path.exists():
        print(f"Warning: src directory not found: {src_path}")
        return
    
    # Scan all modules within the src directory
    for module_dir in src_path.iterdir():
        # Exclude hidden files and __pycache__, etc.
        if module_dir.name.startswith("_") or module_dir.name.startswith("."):
            continue
            
        if not module_dir.is_dir():
            continue
        
        # Check for infrastructure/database/models path
        models_path = module_dir / "infrastructure" / "database" / "models"
        
        if not models_path.exists() or not models_path.is_dir():
            continue
        
        # Verify it is a valid package by checking for __init__.py
        init_file = models_path / "__init__.py"
        if not init_file.exists():
            continue
        
        # Convert directory path to Python import path
        module_name = f"src.{module_dir.name}.infrastructure.database.models"
        
        try:
            # Import the module
            models_module = importlib.import_module(module_name)
            
            # Recursively import all submodules within this module
            for _, submodule_name, _ in pkgutil.walk_packages(
                models_module.__path__, models_module.__name__ + "."
            ):
                try:
                    importlib.import_module(submodule_name)
                    print(f"Model module loaded: {submodule_name}")
                except Exception as e:
                    print(f"Warning: Failed to load {submodule_name} - {e}")
        except Exception as e:
            print(f"Warning: Failed to load {module_name} - {e}")
    
    print("=" * 100)
    print("All models loaded successfully")
    print("=" * 100)
