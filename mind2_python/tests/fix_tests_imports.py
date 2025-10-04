import os

def fix_tests_imports(root="tests"):
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            path = os.path.join(dirpath, fname)
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                content = "".join(lines)

            if "SimpleNamespace" in content and "from types import SimpleNamespace" not in content:
                print(f"[FIX] {path}")
                # หาตำแหน่ง insert หลังสุดของบรรทัด import
                insert_at = 0
                for i, line in enumerate(lines):
                    if line.strip().startswith("import") or line.strip().startswith("from"):
                        insert_at = i + 1
                lines.insert(insert_at, "from types import SimpleNamespace\n")
                with open(path, "w", encoding="utf-8") as f:
                    f.writelines(lines)
            else:
                print(f"[OK ] {path}")

if __name__ == "__main__":
    fix_tests_imports("tests")
