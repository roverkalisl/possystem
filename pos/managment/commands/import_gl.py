import openpyxl
from django.core.management.base import BaseCommand
from pos.models import GLMaster


class Command(BaseCommand):
    help = "Import GL accounts from Excel"

    def add_arguments(self, parser):
        parser.add_argument('file', type=str)

    def handle(self, *args, **kwargs):
        file_path = kwargs['file']

        wb = openpyxl.load_workbook(file_path)
        ws = wb.active

        created = 0
        skipped = 0

        for row in ws.iter_rows(min_row=2, values_only=True):
            gl_code = str(row[0]).strip() if row[0] else None
            gl_name = str(row[1]).strip() if row[1] else None
            gl_type = str(row[2]).strip().lower() if row[2] else None
            parent_group = str(row[3]).strip() if row[3] else ""

            if not gl_code or not gl_name:
                continue

            if GLMaster.objects.filter(gl_code=gl_code).exists():
                skipped += 1
                self.stdout.write(f"Skipped: {gl_code}")
                continue

            GLMaster.objects.create(
                gl_code=gl_code,
                gl_name=gl_name,
                gl_type=gl_type if gl_type in ['asset','liability','equity','income','expense'] else 'expense',
                parent_group=parent_group,
                is_active=True
            )

            created += 1
            self.stdout.write(self.style.SUCCESS(f"Added: {gl_code}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done → Created: {created}, Skipped: {skipped}"
        ))