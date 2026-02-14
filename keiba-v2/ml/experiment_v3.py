"""後方互換: python -m ml.experiment_v3 → ml.experiment にリダイレクト"""
from ml.experiment import *  # noqa: F401,F403

if __name__ == "__main__":
    from ml.experiment import main
    main()
