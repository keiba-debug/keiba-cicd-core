import sys
import os

# プロジェクトルートをパスに追加（scriptsの親ディレクトリ）
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.integrator.race_data_integrator import RaceDataIntegrator


def main():
    race_id = sys.argv[1] if len(sys.argv) > 1 else "202501010101"
    integrator = RaceDataIntegrator()
    path = integrator._get_integrated_file_path(race_id)
    print(path)


if __name__ == "__main__":
    main()


