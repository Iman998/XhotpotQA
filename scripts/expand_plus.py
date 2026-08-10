from xhotpotqa.cli import main

raise SystemExit(main(["expand-plus", *__import__("sys").argv[1:]]))
