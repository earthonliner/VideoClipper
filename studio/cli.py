import argparse
import json

from . import analytics, doctor, project, render, voice, youtube


def _print(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(prog="studio", description="Video studio pipeline CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor", help="check environment")
    sub.add_parser("auth", help="authorize YouTube (opens browser)")
    sub.add_parser("list", help="list projects")
    p = sub.add_parser("new", help="create a project")
    p.add_argument("topic")
    for name in ("status", "tts", "render", "upload"):
        sub.add_parser(name).add_argument("slug")
    p = sub.add_parser("approve", help="approve a gate yourself")
    p.add_argument("slug")
    p.add_argument("gate", choices=project.GATES)
    p.add_argument("--note", default="")
    p = sub.add_parser("sync", help="pull YouTube analytics into data/studio.db")
    p.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    if args.cmd == "doctor":
        _print(doctor.run())
    elif args.cmd == "auth":
        youtube.credentials(interactive=True)
        print("authorized; token saved to .secrets/token.json")
    elif args.cmd == "list":
        _print(project.list_projects())
    elif args.cmd == "new":
        _print(project.create_project(args.topic))
    elif args.cmd == "status":
        _print(project.status(args.slug))
    elif args.cmd == "tts":
        _print(voice.generate_voiceover(args.slug))
    elif args.cmd == "render":
        _print(render.render(args.slug))
    elif args.cmd == "upload":
        _print(youtube.upload(args.slug))
    elif args.cmd == "approve":
        _print(project.approve(args.slug, args.gate, args.note))
    elif args.cmd == "sync":
        _print(analytics.sync(args.limit))


if __name__ == "__main__":
    main()
