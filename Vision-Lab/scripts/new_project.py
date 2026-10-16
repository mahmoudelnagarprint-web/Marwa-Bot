#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سكربت مساعدة لإنشاء مشروع جديد في مساحة فيجن (Vision-Lab).
الاستخدام:
    python scripts\new_project.py اسم-المشروع
ينشئ مجلدًا تحت projects\الاسم\ مع:
- تهيئة Git أولية (git init)
- ملف README.md أولي
- ملف .gitignore أساسي
- مجلد src\ بملف .gitkeep لتتبع المجلد
بعد الإنشاء، يُنصح بالدخول إلى المجلد وإجراء أول commit.
"""

import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("الاستخدام: python scripts\\new_project.py اسم-المشروع")
        print("مثال: python scripts\\new_project.py my-app")
        sys.exit(1)

    project_name = sys.argv[1].strip()
    if not project_name:
        print("خطأ: اسم المشروع لا يمكن أن يكون فارغًا.")
        sys.exit(1)

    # Base directory
    base_dir = Path(__file__).resolve().parent.parent
    projects_dir = base_dir / "projects"
    project_dir = projects_dir / project_name

    # Ensure projects directory exists
    projects_dir.mkdir(parents=True, exist_ok=True)

    if project_dir.exists():
        print(f"خطأ: المجلد {project_dir} موجود بالفعل. اختر اسمًا آخر أو احذفه أولًا.")
        sys.exit(1)

    try:
        # Create project directory
        project_dir.mkdir(parents=True)

        # Create .gitignore
        gitignore_content = """# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.egg/
.installed/
*.egg-info

# Installer logs
pip-log.txt
pip-delete-this-directory.txt

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Spyder project files
.spyderproject
.spyproject

# Rope project files
.ropeproject

# mkdocs documentation
/site

# mypy
.mypy_cache/
.dmypy.json
.dmypy.temp

# PyInstaller
#  Usually these files are written by a python script from a template
#  before PyInstaller builds the exe, so as to inject date/other infos into it.
*.manifest
*.spec

# Installer logs
pip-log.txt
pip-delete-this-directory.txt

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/

# Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# IDE
.vscode/
.idea/
*.sublime-project
*.sublime-workspace
"""
        (project_dir / ".gitignore").write_text(gitignore_content, encoding="utf-8")

        # Create README.md
        readme_content = f"""# {project_name}

تم إنشاء هذا المشروع في {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.
"""
        (project_dir / "README.md").write_text(readme_content, encoding="utf-8")

        # Create src directory with .gitkeep to track the folder
        src_dir = project_dir / "src"
        src_dir.mkdir()
        (src_dir / ".gitkeep").write_text("", encoding="utf-8")

        # Initialize git
        subprocess.run(["git", "init"], cwd=project_dir, check=True)
        subprocess.run(["git", "add", "."], cwd=project_dir, check=True)
        subprocess.run(["git", "commit", "-m", f"Initial commit: إنشاء المشروع {project_name}"], cwd=project_dir, check=True)

        print(f"✅ تم إنشاء المشروع بنجاح: {project_dir}")
        print("الخطوات التالية:")
        print(f"  cd {project_dir}")
        print("  # عدل الملفات وأضف كودك")
        print("  git add .")
        print("  git commit -m \"وصف التحديث\"")
        print("  # اختياري: أضف remote إلى حسابك على GitHub ثم دفع التحديثات")
        print("  # مثال:")
        print("  # git remote add origin https://github.com/اسم-المستخدم/اسم-المستودع.git")
        print("  # git branch -M main")
        print("  # git push -u origin main")
    except subprocess.CalledProcessError as e:
        print(f"خطأ أثناء تنفيذ أمر Git: {e}")
        # Clean up partially created directory?
        try:
            # Remove the project directory if git init failed after creation
            if project_dir.exists():
                import shutil
                shutil.rmtree(project_dir)
        except Exception:
            pass
        sys.exit(1)
    except Exception as e:
        print(f"خطأ غير متوقع: {e}")
        try:
            if project_dir.exists():
                import shutil
                shutil.rmtree(project_dir)
        except Exception:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()