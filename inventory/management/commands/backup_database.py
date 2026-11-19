from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections


class Command(BaseCommand):
    help = "PostgreSQL veritabanını özel formatta yedekler."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default=str(settings.BASE_DIR / "backups"),
            help="Yedeklerin yazılacağı klasör (varsayılan: proje/backups).",
        )
        parser.add_argument(
            "--keep",
            type=int,
            default=30,
            help="Başarılı yedekten sonra tutulacak en fazla yedek sayısı; 0 sınırsızdır.",
        )

    def handle(self, *args, **options):
        connection = connections["default"]
        db = connection.settings_dict
        if db["ENGINE"] != "django.db.backends.postgresql":
            raise CommandError("Bu komut yalnızca PostgreSQL veritabanlarında çalışır.")
        if options["keep"] < 0:
            raise CommandError("--keep sıfır veya pozitif olmalıdır.")

        pg_dump = shutil.which("pg_dump")
        if not pg_dump:
            raise CommandError("pg_dump bulunamadı. PostgreSQL istemci araçlarını yükleyip PATH ayarını kontrol edin.")

        output_dir = Path(options["output_dir"]).expanduser().resolve()
        try:
            output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            if os.name == "posix":
                output_dir.chmod(0o700)
        except OSError as exc:
            raise CommandError(f"Yedek klasörü oluşturulamadı: {exc}") from exc

        timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
        final_path = output_dir / f"it-envanter-{timestamp}.dump"
        temp_path = None
        env = os.environ.copy()
        if db.get("PASSWORD"):
            env["PGPASSWORD"] = str(db["PASSWORD"])

        command = [pg_dump, "--format=custom", "--no-owner", "--dbname", str(db["NAME"])]
        if db.get("USER"):
            command.extend(["--username", str(db["USER"])])
        if db.get("HOST"):
            command.extend(["--host", str(db["HOST"])])
        if db.get("PORT"):
            command.extend(["--port", str(db["PORT"])])

        try:
            with tempfile.NamedTemporaryFile(
                prefix=".it-envanter-", suffix=".tmp", dir=output_dir, delete=False
            ) as temp_file:
                temp_path = Path(temp_file.name)
            subprocess.run(
                [*command[:3], "--file", str(temp_path), *command[3:]],
                check=True,
                env=env,
                capture_output=True,
                text=True,
            )
            if temp_path.stat().st_size == 0:
                raise CommandError("pg_dump boş bir yedek oluşturdu.")
            if os.name == "posix":
                temp_path.chmod(0o600)
            temp_path.replace(final_path)
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or "").strip()
            raise CommandError(f"pg_dump başarısız oldu: {detail or 'ayrıntı yok'}") from exc
        except OSError as exc:
            raise CommandError(f"Yedek dosyası yazılamadı: {exc}") from exc
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink(missing_ok=True)

        if options["keep"]:
            backups = sorted(output_dir.glob("it-envanter-*.dump"), key=lambda path: path.stat().st_mtime, reverse=True)
            for old_backup in backups[options["keep"] :]:
                old_backup.unlink()

        self.stdout.write(self.style.SUCCESS(f"Yedek oluşturuldu: {final_path}"))
