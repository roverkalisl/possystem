import pandas as pd
from django.core.management.base import BaseCommand
from pos.models import GLMaster


class Command(BaseCommand):
    help = "Import GL from Excel"

    def add_arguments(self, parser):
        parser.add_argument("file", type=str, help="Excel file path")

    def handle(self, *args, **kwargs):
        file_path = kwargs["file"]

        try:
            df = pd.read_excel(file_path)

            for _, row in df.iterrows():
                gl_code = str(row["gl_code"]).strip()

                GLMaster.objects.update_or_create(
                    gl_code=gl_code,
                    defaults={
                        "gl_name": row["gl_name"],
                        "gl_type": row["gl_type"],
                        "parent_group": row.get("parent_group", ""),
                        "is_active": True
                    }
                )

            self.stdout.write(self.style.SUCCESS("✅ GL Import Completed"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error: {str(e)}"))