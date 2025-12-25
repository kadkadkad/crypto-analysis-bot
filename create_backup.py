import os
import shutil
from datetime import datetime

# Configuration
SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_ROOT = os.path.join(SOURCE_DIR, "backup")
IGNORE_DIRS = {'.git', '.idea', '.venv', '__pycache__', 'backup', 'artifacts'}
IGNORE_EXTENSIONS = {'.pyc', '.log', '.DS_Store'}

def create_backup():
    # Create unique timestamped folder
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dest_dir = os.path.join(BACKUP_ROOT, f"backup_{timestamp}")
    
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
        print(f"[INFO] Created backup directory: {dest_dir}")

    file_count = 0
    
    # Walk through source directory
    for root, dirs, files in os.walk(SOURCE_DIR):
        # Remove ignored directories from traversal
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            file_ext = os.path.splitext(file)[1]
            if file_ext in IGNORE_EXTENSIONS:
                continue
                
            src_path = os.path.join(root, file)
            
            # Calculate relative path to maintain structure
            rel_path = os.path.relpath(src_path, SOURCE_DIR)
            dest_path = os.path.join(dest_dir, rel_path)
            
            # Ensure destination directory exists
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            
            try:
                shutil.copy2(src_path, dest_path)
                file_count += 1
            except Exception as e:
                print(f"[ERROR] Failed to copy {file}: {e}")

    print(f"\n✅ Backup completed successfully!")
    print(f"📂 Location: {dest_dir}")
    print(f"📄 Files backed up: {file_count}")

if __name__ == "__main__":
    create_backup()
