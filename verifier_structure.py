import os

base = r"C:\Users\m.astitou\Desktop\selenuim\sage-x3-rpa"

files_to_check = [
    "config/__init__.py",
    "config/settings.py",
    "core/__init__.py",
    "core/logger.py",
    "core/driver_manager.py",
    "core/sage_connector.py",
    "core/base_robot.py",
    "modules/__init__.py",
    "modules/lettrage/__init__.py",
    "modules/lettrage/lettrage_robot.py",
    "modules/facturation/__init__.py",
    "modules/reporting/__init__.py",
    "utils/__init__.py",
    "utils/excel_handler.py",
    "scripts/__init__.py",
    "scripts/run_lettrage.py",
    ".env",
    ".gitignore",
    "requirements.txt",
    "README.md",
    "QUICKSTART.md",
    "test_lettrage.py"
]

print("🔍 Vérification de la structure...\n")
missing = []
present = []

for file in files_to_check:
    full_path = os.path.join(base, file)
    if os.path.exists(full_path):
        present.append(file)
        print(f"✅ {file}")
    else:
        missing.append(file)
        print(f"❌ {file} MANQUANT")

print(f"\n📊 Résumé:")
print(f"   ✅ Présents: {len(present)}/{len(files_to_check)}")
print(f"   ❌ Manquants: {len(missing)}/{len(files_to_check)}")

if len(missing) == 0:
    print("\n🎉 STRUCTURE COMPLÈTE !")
else:
    print(f"\n⚠️  Fichiers manquants: {missing}")

input("\nAppuyez sur Entrée pour fermer...")
