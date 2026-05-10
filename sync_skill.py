"""
sync_skill.py — Synchronise le skill portfolio-analyst entre user-level et project-level.

Architecture (cf CHANGELOG v1.6.0) :
  Master éditable     : ~/.claude/skills/portfolio-analyst/   (user-level, où tu modifies)
  Copie déployable    : ./.claude/skills/portfolio-analyst/   (project-level, committable)

Direction : user-level → project-level (master vers copie).

Pourquoi cette direction :
  - Claude Code charge en priorité le user-level (hiérarchie personal > project)
  - L'utilisateur édite naturellement le user-level depuis ses sessions Claude Code
  - Le project-level doit être committable pour que portfolio_agent.py le lise
    sur le runner GitHub Actions (où le user-level n'existe pas)

Usage :
  python sync_skill.py            → synchronise et affiche le diff
  python sync_skill.py --check    → vérifie la sync sans modifier (CI / pre-commit)

À faire avant chaque commit qui touche le skill : exécute ce script puis git add .claude/skills/.
Tu peux aussi installer un git pre-commit hook (cf README ou doc).
"""

from pathlib import Path
import shutil
import sys
import filecmp

SKILL_NAME = "portfolio-analyst"
SOURCE = Path.home() / ".claude" / "skills" / SKILL_NAME
TARGET = Path(__file__).parent / ".claude" / "skills" / SKILL_NAME


def list_files(root):
    """Liste récursive des fichiers (chemins relatifs) sous root."""
    if not root.exists():
        return set()
    return {p.relative_to(root) for p in root.rglob("*") if p.is_file()}


def diff_dirs(src, dst):
    """Retourne (added, removed, modified) entre src et dst."""
    src_files = list_files(src)
    dst_files = list_files(dst)
    added    = src_files - dst_files
    removed  = dst_files - src_files
    common   = src_files & dst_files
    modified = {f for f in common if not filecmp.cmp(src / f, dst / f, shallow=False)}
    return added, removed, modified


def main():
    check_only = "--check" in sys.argv

    if not SOURCE.exists():
        print(f"❌ Source absente : {SOURCE}")
        print(f"   Le user-level skill n'existe pas. Rien à synchroniser.")
        sys.exit(1)

    added, removed, modified = diff_dirs(SOURCE, TARGET)

    if not (added or removed or modified):
        print(f"✅ Sync OK — {SOURCE} et {TARGET} identiques")
        return

    print(f"📋 Différences détectées entre {SOURCE} et {TARGET} :")
    for f in sorted(added):
        print(f"   + {f}  (présent en source, absent en target)")
    for f in sorted(removed):
        print(f"   - {f}  (absent en source, présent en target)")
    for f in sorted(modified):
        print(f"   ~ {f}  (modifié)")

    if check_only:
        print(f"\n⚠️  Mode --check : sync nécessaire mais non appliquée")
        print(f"   Exécute : python sync_skill.py")
        sys.exit(1)

    # Apply sync : remove target then copy entirely (gère les suppressions en source)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(SOURCE, TARGET)

    n_files = sum(1 for _ in TARGET.rglob("*") if _.is_file())
    print(f"\n✅ Sync appliquée : {SOURCE} → {TARGET}")
    print(f"   {n_files} fichier(s) total")
    print(f"   Pense à : git add .claude/skills/  (puis commit)")


if __name__ == "__main__":
    main()
