from django.core.management.base import BaseCommand
from io import BytesIO
try:
    import openpyxl
except Exception:
    openpyxl = None


class Command(BaseCommand):
    help = 'Run a sample budget import using an in-memory Excel file'

    def add_arguments(self, parser):
        parser.add_argument('--project', required=True, help='Project ID to import into (project.project_id)')
        parser.add_argument('--create-missing-gl', action='store_true')

    def handle(self, *args, **options):
        if openpyxl is None:
            self.stderr.write('openpyxl is required to run this command')
            return

        from pos.models import Project
        from pos.cost_analysis_views import process_budget_excel

        proj_code = options['project']
        create_missing = options['create_missing_gl']

        project, created = Project.objects.get_or_create(
            project_id=proj_code,
            defaults={
                'project_name': f'Test Project {proj_code}',
                'project_type': 'OT'
            }
        )
        if created:
            self.stdout.write(f'Created test project {proj_code}')

        # Build an in-memory workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['Project', 'GL Code', 'GL Name', 'Budget Amount'])
        ws.append([proj_code, '5101', 'Cement', 100000])
        ws.append([proj_code, '5101', 'Cement', 25000])  # duplicate to test consolidation
        ws.append([proj_code, '5200', 'Skilled Labour', 50000])

        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)

        success_count, errors, projects = process_budget_excel(project, buf, replace_existing=True, create_missing_gl=create_missing, import_multiple_projects=False, user=None)

        self.stdout.write(f'Success: {success_count}, Projects updated: {projects}')
        if errors:
            self.stdout.write('Errors:')
            for e in errors:
                self.stdout.write(' - ' + str(e))
