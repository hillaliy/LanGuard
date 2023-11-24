from django.core.management.base import BaseCommand
from core.models import Device
from django.core.serializers import serialize, deserialize


class ExportDB(BaseCommand):
    help = "Export data to a JSON file"

    def handle(self, *args, **options):
        data = serialize("json", Device.objects.all())
        with open("lan_guard_data.json", "w") as file:
            file.write(data)
        self.stdout.write(self.style.SUCCESS("Data exported successfully!"))


class ImportDB(BaseCommand):
    help = "Import data from a JSON file"

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="Path to the import file")

    def handle(self, *args, **options):
        file_path = options["file_path"]
        with open(file_path, "r") as file:
            data = file.read()
            deserialized_data = list(deserialize("json", data))
            for obj in deserialized_data:
                obj.save()
        self.stdout.write(self.style.SUCCESS("Data imported successfully!"))
