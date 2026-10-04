from __future__ import annotations

import argparse
import getpass
import logging
import sys
from logging.handlers import RotatingFileHandler

from . import app, notify
from .client import boletim_url
from .state import data_dir


def configure_logging() -> None:
    handlers: list[logging.Handler] = [
        RotatingFileHandler(data_dir() / "notifier.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    ]
    # pythonw.exe (used by the scheduled task) has no console, so sys.stderr is None there
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", handlers=handlers)


def main() -> None:
    parser = argparse.ArgumentParser(prog="suap_notifier", description="Notifica mudanças no boletim do SUAP (IFSP).")
    sub = parser.add_subparsers(dest="command")
    run_parser = sub.add_parser("run", help="verifica o boletim e notifica mudanças (padrão)")
    run_parser.add_argument("--dry-run", action="store_true", help="mostra o boletim lido sem salvar nem notificar")
    sub.add_parser("setup", help="salva prontuário e senha e cria o estado inicial")
    sub.add_parser("login", help="abre o Edge para login manual quando o automático falhar")
    sub.add_parser("test-notification", help="mostra uma notificação de teste")
    args = parser.parse_args()

    configure_logging()
    log = logging.getLogger("suap_notifier")
    command = args.command or "run"

    if command == "setup":
        prontuario = input("Prontuário: ")
        password = getpass.getpass("Senha do SUAP: ")
        print("Entrando no SUAP pelo Edge (uma janela pode aparecer por alguns segundos)...")
        count = app.setup(prontuario, password)
        print(f"Pronto: {count} disciplina(s) no boletim atual. Dados em {data_dir()}")
    elif command == "login":
        print("Faça login na janela do Edge que vai abrir.")
        app.interactive_login()
        print("Sessão salva.")
    elif command == "test-notification":
        creds = app.Credentials.load()
        url = boletim_url(creds.prontuario) if creds else None
        notify.show("SUAP Notifier", ["Notificação de teste. Clique para abrir o boletim."], url)
    elif args.dry_run:
        for subject in app.dry_run().subjects.values():
            print(f"{subject.diario} {subject.name} | {subject.situacao} | faltas {subject.faltas} | {subject.averages}")
            for assessment in subject.assessments.values():
                print(f"    {assessment.etapa} {assessment.sigla} ({assessment.tipo}): {assessment.nota or '-'}")
    else:
        try:
            app.run()
        except Exception:
            log.exception("unexpected failure")
            raise


if __name__ == "__main__":
    main()
