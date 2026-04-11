from main.prelaunch import prepare_prelaunch


def _run() -> None:
    prepare_prelaunch()
    from main.entry import main as run_main

    run_main()


if __name__ == "__main__":
    _run()
